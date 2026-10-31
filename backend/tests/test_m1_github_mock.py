"""M1-C GitHub URL validation + mocked-flow tests (no network) + classification."""
import io
import json
import tarfile

import httpx
import pytest

from app.services.classify import _classify_c, _classify_python
from app.services.github_import import GitHubClient, ImportError_, import_github, validate_github_url


BAD_URLS = [
    "http://github.com/owner/repo",                    # non-https
    "https://github.com.evil.com/owner/repo",          # deceptive host
    "https://evil.com/github.com/owner/repo",          # wrong host
    "https://127.0.0.1/owner/repo",                    # IP literal
    "https://user:pass@github.com/owner/repo",         # userinfo
    "https://github.com:8443/owner/repo",              # port
    "https://github.com/owner/repo?x=1",               # query
    "https://github.com/owner/repo#frag",              # fragment
    "https://github.com/../owner/repo",                # traversal
    "https://github.com/owner/repo/tree/main/x",       # deep path unsupported
    "https://github.com/owner/repo.git",               # .git suffix
    "https://github.com/owner/",                       # missing repo
    "https://github.com/ow!ner/repo",                  # bad chars
    "ftp://github.com/owner/repo",                     # scheme
    "",                                                # empty
]


@pytest.mark.parametrize("url", BAD_URLS)
def test_bad_urls_rejected(url):
    with pytest.raises(ImportError_):
        validate_github_url(url)


def test_good_url_parses():
    p = validate_github_url("https://github.com/antirez/kilo")
    assert (p.owner, p.repo) == ("antirez", "kilo")


def _tar_gz(prefix: str, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            ti = tarfile.TarInfo(f"{prefix}/{name}")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def _mock_client(handler) -> GitHubClient:
    return GitHubClient(transport=httpx.MockTransport(handler))


def _ok_targz_repo():
    """Happy-path mock handler with SHA pinning data."""
    sha = "a" * 40
    blob = _tar_gz(f"kilo-{sha}", {"kilo.c": b"int main(void){return 0;}\n",
                                   "README.md": b"# kilo\n"})

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://api.github.com/repos/antirez/kilo":
            return httpx.Response(200, json={"full_name": "antirez/kilo",
                                             "default_branch": "master", "size": 1})
        if url == "https://api.github.com/repos/antirez/kilo/commits/master":
            return httpx.Response(200, json={"sha": sha})
        if url == f"https://codeload.github.com/antirez/kilo/tar.gz/{sha}":
            return httpx.Response(200, content=blob)
        return httpx.Response(404)

    return sha, handler


def test_github_mock_happy_path_and_pinning(store, monkeypatch):
    import app.services.github_import as gh
    sha, handler = _ok_targz_repo()

    class PinnedClient(GitHubClient):
        def __init__(self):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(gh, "GitHubClient", PinnedClient)
    result = gh.import_github(store, "https://github.com/antirez/kilo")
    assert result["commit_sha"] == sha and len(result["commit_sha"]) == 40
    assert result["canonical_owner"] == "antirez" and result["canonical_repo"] == "kilo"
    assert result["file_count"] == 2
    rec = store.query_one("SELECT * FROM imports WHERE id=?", (result["import_id"],))
    assert rec["status"] == "completed" and rec["commit_sha"] == sha
    assert rec["archive_sha256"] == result["archive_sha256"]
    targets = store.query("SELECT * FROM compilation_targets WHERE snapshot_id=?",
                          (result["snapshot_id"],))
    assert any(t["status"] == "COMPILATION_CANDIDATE" and t["primary_file"] == "kilo.c"
               for t in targets)


def test_github_mock_redirect_to_evil_host_rejected(store, monkeypatch):
    import app.services.github_import as gh

    def handler(request):
        return httpx.Response(302, headers={"location": "https://evil.example.com/repos/x"})

    class C(GitHubClient):
        def __init__(self):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(gh, "GitHubClient", C)
    with pytest.raises(ImportError_) as ei:
        gh.import_github(store, "https://github.com/antirez/kilo")
    assert ei.value.code == "REDIRECT_DISALLOWED"


def test_github_mock_rate_limited(store, monkeypatch):
    import app.services.github_import as gh

    def handler(request):
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, json={})

    class C(GitHubClient):
        def __init__(self):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(gh, "GitHubClient", C)
    with pytest.raises(ImportError_) as ei:
        gh.import_github(store, "https://github.com/antirez/kilo")
    assert ei.value.code == "RATE_LIMITED"


def test_github_mock_not_found_and_bad_ref(store, monkeypatch):
    import app.services.github_import as gh

    def handler(request):
        return httpx.Response(404, json={"message": "Not Found"})

    class C(GitHubClient):
        def __init__(self):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(gh, "GitHubClient", C)
    with pytest.raises(ImportError_) as ei:
        gh.import_github(store, "https://github.com/antirez/nope")
    assert ei.value.code == "REPO_NOT_FOUND"
    rec = store.query("SELECT * FROM imports WHERE status='failed'")
    assert len(rec) == 1 and rec[0]["error_code"] == "REPO_NOT_FOUND"


def test_github_mock_oversized_repo_rejected(store, monkeypatch):
    import app.services.github_import as gh

    def handler(request):
        return httpx.Response(200, json={"full_name": "o/r", "default_branch": "m",
                                         "size": 10_000_000})

    class C(GitHubClient):
        def __init__(self):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(gh, "GitHubClient", C)
    with pytest.raises(ImportError_) as ei:
        gh.import_github(store, "https://github.com/o/r")
    assert ei.value.code == "REPO_TOO_LARGE"


# ------------------------- classification (M1-D) -------------------------

def test_classification_python_script_stdlib_entry():
    diag: list = []
    t = _classify_python("app.py", b'import sys\nif __name__ == "__main__":\n    sys.exit(0)\n', diag)
    assert t["status"] == "EXECUTABLE_CANDIDATE"
    codes = {r["code"] for r in t["reasons"]}
    assert "entry-guard-detected" in codes and "stdlib-only-entry" in codes
    assert all(r["verified"] is False for r in t["reasons"] if r["code"] == "stdlib-only-entry")


def test_classification_python_nonstdlib_withheld():
    diag: list = []
    t = _classify_python("app.py", b"import requests\nprint(requests)\n", diag)
    assert t["status"] == "STATIC_ANALYZABLE"
    assert any(r["code"] == "unverified-dependencies" for r in t["reasons"])


def test_classification_python_syntax_error_recorded():
    diag: list = []
    t = _classify_python("bad.py", b"def broken(:\n    pass\n", diag)
    assert t["status"] == "STATIC_ANALYZABLE"
    assert any(r["code"] == "syntax-invalid" for r in t["reasons"])
    assert diag and diag[0][1] == "PY_SYNTAX_INVALID"


def test_classification_c_no_main_never_compilation_candidate():
    t = _classify_c("util.c", b"int add(int a, int b){return a+b;}\n", ["util.c"])
    assert t["status"] == "STATIC_ANALYZABLE"
    t2 = _classify_c("hdr.h", b"#pragma once\n", ["hdr.h"])
    assert t2["kind"] == "c_header" and t2["status"] == "STATIC_ANALYZABLE"


def test_main_detection_is_lexical_not_semantic():
    """'main(' inside a comment IS matched by the lexical probe — this is why the
    reason carries verified=False; semantic verification requires real toolchain
    checks (M2+). The UI/status must never present this as verified runnability."""
    t = _classify_c("weird.c", b"// main( appears only in a comment\nint x;\n", ["weird.c"])
    assert t["status"] == "COMPILATION_CANDIDATE"
    reason = next(r for r in t["reasons"] if r["code"] == "main-detected")
    assert reason["verified"] is False
