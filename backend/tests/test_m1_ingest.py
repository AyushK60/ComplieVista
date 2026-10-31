"""M1-B ingestion tests: paste/upload/zip happy paths, limits, idempotency, persistence,
and adversarial no-execution proof."""
import io
import zipfile

import pytest

from app.services.archive import extract_zip
from app.services.ingest import IngestError, ingest_files, ingest_paste, ingest_zip

PY_MAIN = b'print("hi")\nif __name__ == "__main__":\n    print("main")\n'
C_MAIN = b"#include <stdio.h>\nint main(void){return 0;}\n"


def make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_paste_python_and_c(store):
    r = ingest_paste(store, "python", "hello.py", PY_MAIN)
    assert r["file_count"] == 1 and r["existed"] is False
    snap = store.query_one("SELECT * FROM source_snapshots WHERE id=?", (r["snapshot_id"],))
    assert snap["origin"] == "paste"
    r2 = ingest_paste(store, "c", "prog.c", C_MAIN)
    targets = store.query("SELECT * FROM compilation_targets WHERE snapshot_id=?",
                          (r2["snapshot_id"],))
    assert any(t["status"] == "COMPILATION_CANDIDATE" for t in targets)


def test_paste_limit_rejected(store):
    with pytest.raises(IngestError):
        ingest_paste(store, "python", "big.py", b"x" * (513 * 1024))


def test_zip_ingest_and_idempotent_reimport(store):
    data = make_zip({"src/a.py": b"x = 1\n", "src/b.c": C_MAIN, "docs/readme.md": b"# r\n"})
    r = ingest_zip(store, data)
    assert r["file_count"] == 3
    # Same bytes uploaded into the same project → idempotent (same snapshot identity)
    store.execute("DELETE FROM projects WHERE id=?", (r["project_id"],))
    # simulate re-import within same project by direct store path:
    snap2, existed = store.insert_snapshot(r["project_id"], "zip",
                                           {"src/a.py": b"x = 1\n", "src/b.c": C_MAIN,
                                            "docs/readme.md": b"# r\n"})
    assert existed is True and snap2 == r["snapshot_id"]
    files = store.query("SELECT * FROM source_files WHERE snapshot_id=?", (r["snapshot_id"],))
    assert all(len(f["content_sha256"]) == 64 for f in files)
    # artifact round-trip
    f0 = files[0]
    assert store.get_artifact(f0["content_sha256"]) is not None


def test_upload_individual_files(store):
    r = ingest_files(store, [("one.c", C_MAIN), ("two.py", PY_MAIN)])
    assert r["file_count"] == 2


def test_upload_rejects_non_source(store):
    with pytest.raises(IngestError):
        ingest_files(store, [("evil.sh", b"#!/bin/sh\nrm -rf /\n")])


def test_no_python_execution_during_ingest(store, tmp_path):
    """Adversarial: top-level side effects and import-time bombs must NOT run."""
    marker = tmp_path / "PWNED_MARKER"
    adversarial = (b"import pathlib\n"
                   b"raise RuntimeError('import-time bomb')\n"
                   b"pathlib.Path(r'" + str(marker).encode() + b"').write_text('x')\n")
    r = ingest_paste(store, "python", "bomb.py", adversarial)
    assert r["file_count"] == 1
    assert not marker.exists(), "top-level code executed during ingestion!"


def test_zip_rejects_no_acceptable_files(store):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("only.bin", b"\x00\x01\x02binary")
    with pytest.raises(IngestError):
        ingest_zip(store, buf.getvalue())


def test_persistence_across_reopen(tmp_path):
    from app.store.db import Store
    data_dir = tmp_path / "data"
    s1 = Store(data_dir=data_dir)
    r = ingest_paste(s1, "python", "x.py", b"value = 42\n")
    s1.close()
    s2 = Store(data_dir=data_dir)
    files = s2.query("SELECT rel_path, content_sha256 FROM source_files WHERE snapshot_id=?",
                     (r["snapshot_id"],))
    assert len(files) == 1
    assert s2.query_one("SELECT value FROM meta WHERE key='schema_version'")["value"] == "m1.v1"
