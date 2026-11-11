"""Stage 1-C safe public GitHub repository import.

Policy (docs/SECURITY.md + the project notes):
 - Only structurally valid https://github.com/OWNER/REPO URLs (optional ?ref= is a
   separate API field, never URL-interpolated). Userinfo, ports, non-GitHub hosts,
   deceptive hostnames, IPs, queries/fragments, control chars are rejected.
 - Metadata + commit SHA resolution via fixed api.github.com routes; archive only
   from codeload.github.com pinned to the FULL commit SHA.
 - Manual redirect handling with a strict host allowlist; no sensitive headers
   forwarded anywhere; bounded timeouts and streaming byte caps.
 - Build metadata (Makefile/CMakeLists/pyproject) is treated as inert data.
 - NOTHING retrieved is ever executed, imported or built during import.
"""
from __future__ import annotations

import hashlib
import io
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import IMPORT_POLICY_VERSION, LIMITS
from app.services import archive as archive_mod
from app.store.db import Store, new_id, now_utc

ALLOWED_API_HOST = "api.github.com"
ALLOWED_ARCHIVE_HOST = "codeload.github.com"
_REDIRECT_HOST_ALLOWLIST = {
    "github.com", "www.github.com", "api.github.com", "codeload.github.com",
    "objects.githubusercontent.com", "raw.githubusercontent.com",
}
_OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ImportError_(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


ImportError = ImportError_  # typed import error (distinct from builtin semantics)


@dataclass
class ParsedRepo:
    owner: str
    repo: str
    ref: str | None


def validate_github_url(url: str) -> ParsedRepo:
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise ImportError("INVALID_URL", "URL missing or oversized")
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise ImportError("INVALID_URL", "control characters in URL")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ImportError("INVALID_URL", f"scheme must be https, got {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if host != "github.com":
        raise ImportError("INVALID_URL", f"host must be exactly github.com, got {host!r}")
    if parsed.username or parsed.password:
        raise ImportError("INVALID_URL", "userinfo not allowed")
    if parsed.port:
        raise ImportError("INVALID_URL", "explicit ports not allowed")
    if parsed.query or parsed.fragment:
        raise ImportError("INVALID_URL", "query/fragment not allowed")
    if parsed.params:
        raise ImportError("INVALID_URL", "parameters not allowed")
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        raise ImportError("INVALID_URL", "IP-literal hosts not allowed")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ImportError("INVALID_URL", "path must be /OWNER/REPO")
    owner, repo = parts[0], parts[1]
    for name in (owner, repo):
        if name in ("..", ".") or not _OWNER_REPO_RE.match(name) or name.endswith(".git"):
            raise ImportError("INVALID_URL", f"invalid path segment {name!r}")
    if len(parts) > 2:
        raise ImportError("INVALID_URL",
                          "only /OWNER/REPO is supported; pass the ref via the 'ref' field")
    return ParsedRepo(owner=owner, repo=repo, ref=None)


class GitHubClient:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.limits = LIMITS
        self.client = httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(self.limits["github_api_timeout_s"]),
            headers={"User-Agent": "CompileVista-M1 (+local analysis tool)",
                     "Accept": "application/vnd.github+json"},
            transport=transport,
        )

    def _get(self, url: str, *, stream: bool = False):
        """GET with manual, allowlisted redirect handling. Returns (response, final_url)."""
        current = url
        for _hop in range(4):
            resp = self.client.get(current)
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("location")
                if not loc:
                    raise ImportError("REDIRECT_INVALID", "redirect without Location")
                target = urlparse(loc if "://" in loc else
                                  f"{urlparse(current).scheme}://{urlparse(current).netloc}{loc}")
                if target.scheme != "https" or target.hostname not in _REDIRECT_HOST_ALLOWLIST:
                    raise ImportError("REDIRECT_DISALLOWED",
                                      f"redirect to non-allowlisted host {target.hostname!r}")
                current = str(target)
                continue
            return resp, current
        raise ImportError("TOO_MANY_REDIRECTS", "more than 3 redirects")

    def repo_meta(self, owner: str, repo: str) -> dict:
        resp, _ = self._get(f"https://{ALLOWED_API_HOST}/repos/{owner}/{repo}")
        if resp.status_code == 404:
            raise ImportError("REPO_NOT_FOUND", f"repository {owner}/{repo} not found", 404)
        if resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
            raise ImportError("RATE_LIMITED",
                              "GitHub API rate limit exceeded (unauthenticated)", 429)
        if resp.status_code != 200:
            raise ImportError("UPSTREAM_ERROR", f"GitHub API returned {resp.status_code}", 502)
        data = resp.json()
        if data.get("size", 0) * 1024 > self.limits["github_archive_max_compressed_bytes"] * 4:
            raise ImportError("REPO_TOO_LARGE", "repository reported too large for bounded import")
        return data

    def resolve_sha(self, owner: str, repo: str, ref: str | None,
                    default_branch: str | None) -> str:
        ref = ref or default_branch
        if not ref:
            raise ImportError("REF_UNRESOLVED", "no ref and no default branch reported")
        if not _REF_RE.match(ref) or ".." in ref:
            raise ImportError("INVALID_REF", f"ref rejected: {ref!r}")
        resp, _ = self._get(f"https://{ALLOWED_API_HOST}/repos/{owner}/{repo}/commits/{ref}")
        if resp.status_code in (404, 422):
            raise ImportError("REF_NOT_FOUND", f"ref {ref!r} not found", 404)
        if resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
            raise ImportError("RATE_LIMITED", "GitHub API rate limit exceeded", 429)
        if resp.status_code != 200:
            raise ImportError("UPSTREAM_ERROR", f"GitHub API returned {resp.status_code}", 502)
        sha = resp.json().get("sha", "")
        if not _SHA_RE.match(sha):
            raise ImportError("SHA_INVALID", "GitHub did not return a full 40-hex commit SHA")
        return sha

    def fetch_archive(self, owner: str, repo: str, sha: str) -> bytes:
        url = f"https://{ALLOWED_ARCHIVE_HOST}/{owner}/{repo}/tar.gz/{sha}"
        t0 = time.perf_counter()
        with self.client.stream("GET", url,
                                timeout=self.limits["github_download_timeout_s"]) as resp:
            if resp.status_code == 404:
                raise ImportError("ARCHIVE_NOT_FOUND", "archive not available for this SHA", 404)
            if resp.status_code != 200:
                raise ImportError("UPSTREAM_ERROR", f"archive endpoint returned {resp.status_code}", 502)
            cap = self.limits["github_archive_max_compressed_bytes"]
            buf = io.BytesIO()
            total = 0
            for chunk in resp.iter_bytes(65536):
                total += len(chunk)
                if total > cap:
                    raise ImportError("ARCHIVE_TOO_LARGE",
                                      f"archive exceeds {cap} bytes mid-download")
                buf.write(chunk)
            data = buf.getvalue()
        if not data.startswith(b"\x1f\x8b"):
            raise ImportError("UNEXPECTED_PAYLOAD", "archive payload is not gzip")
        return data


def import_github(store: Store, url: str, ref: str | None = None) -> dict:
    parsed = validate_github_url(url)
    import_id = new_id()
    store.execute(
        "INSERT INTO imports (id, project_id, input_url, ref_requested, status, created_utc,"
        " policy_version) VALUES (?,?,?,?,?,?,?)",
        (import_id, "pending", url, ref, "started", now_utc(), IMPORT_POLICY_VERSION))

    def fail(code: str, message: str, status: int = 400) -> None:
        store.execute(
            "UPDATE imports SET status='failed', error_code=?, retrieval_utc=? WHERE id=?",
            (code, now_utc(), import_id))
        raise ImportError(code, message, status)

    try:
        client = GitHubClient()
        meta = client.repo_meta(parsed.owner, parsed.repo)
        canonical = meta.get("full_name", "")
        if canonical.lower() != f"{parsed.owner}/{parsed.repo}".lower():
            fail("CANONICAL_MISMATCH", f"canonical name {canonical!r} does not match request")
        owner, repo = canonical.split("/")
        sha = client.resolve_sha(owner, repo, ref, meta.get("default_branch"))
        t0 = time.perf_counter()
        archive_bytes = client.fetch_archive(owner, repo, sha)
        dl_ms = int((time.perf_counter() - t0) * 1000)
    except ImportError_ as e:
        fail(e.code, e.message, e.status)
        raise  # unreachable

    result = archive_mod.extract_tar_gz(archive_bytes)
    if not result.files:
        fail("NO_ACCEPTABLE_FILES",
             f"archive contained no acceptable source files ({result.rejected_count} rejected)")

    project_id = new_id()
    store.execute("INSERT INTO projects (id, name, created_utc) VALUES (?,?,?)",
                  (project_id, f"github: {owner}/{repo}@{sha[:8]}", now_utc()))
    store.execute(
        "UPDATE imports SET project_id=?, canonical_owner=?, canonical_repo=?, commit_sha=?,"
        " archive_sha256=?, retrieval_utc=?, status='completed', file_count=?,"
        " rejected_count=? WHERE id=?",
        (project_id, owner, repo, sha, hashlib.sha256(archive_bytes).hexdigest(), now_utc(),
         len(result.files), result.rejected_count, import_id))
    snap_id, existed = store.insert_snapshot(project_id, "github", result.files, import_id)
    from app.services.classify import classify_files, classify_multi_file_hint
    classify_files(store, snap_id, result.files)
    classify_multi_file_hint(store, snap_id, result.files)
    for d in result.rejected[:100]:
        store.execute(
            "INSERT INTO snapshot_diagnostics (id, snapshot_id, file_path, severity, code, detail)"
            " VALUES (?,?,?,?,?,?)",
            (new_id(), snap_id, d.get("entry", "")[:300], "info", d["reason_code"], d.get("detail", "")))
    return {
        "import_id": import_id, "project_id": project_id, "snapshot_id": snap_id,
        "canonical_owner": owner, "canonical_repo": repo, "commit_sha": sha,
        "ref_requested": ref, "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "download_ms": dl_ms, "file_count": len(result.files),
        "rejected_count": result.rejected_count, "existed": existed,
        "policy_version": IMPORT_POLICY_VERSION,
    }
