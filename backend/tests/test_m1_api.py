"""M1 API contract tests: ingestion, projects, targets, imports, M0 regression."""
import io
import tempfile
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.contracts.models import (CompilationTargetModel, ImportManifestModel,
                                  ProjectModel, SourceSnapshotModel)
from app.main import create_app
from app.store.db import Store


@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(store=Store(data_dir=tmp_path / "data")))


def test_limits_endpoint_discloses_bounds(client):
    body = client.get("/api/v1/limits").json()
    assert body["limits"]["paste_max_bytes"] == 512 * 1024
    assert body["limits"]["snapshot_max_files"] == 2000


def test_paste_flow_full_contract(client):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "demo.py",
        "content": "x = 1\nif __name__ == '__main__':\n    print(x)\n"})
    assert r.status_code == 200
    body = r.json()
    proj = client.get(f"/api/v1/projects/{body['project_id']}").json()
    snap_rec = proj["snapshots"][0]
    snap = SourceSnapshotModel(project_id=proj["id"], id=snap_rec["id"],
                               origin=snap_rec["origin"],
                               combined_sha256=snap_rec["combined_sha256"],
                               created_utc=snap_rec["created_utc"])
    assert snap.origin == "paste" and len(snap.combined_sha256) == 64
    sid = body["snapshot_id"]
    detail = client.get(f"/api/v1/projects/{body['project_id']}/snapshots/{sid}").json()
    assert detail["files"][0]["rel_path"] == "demo.py"
    fid = detail["files"][0]["id"]
    f = client.get(f"/api/v1/projects/{body['project_id']}/snapshots/{sid}/files/{fid}").json()
    assert "print(x)" in f["text"]
    targets = client.get(f"/api/v1/projects/{body['project_id']}/targets").json()
    t = CompilationTargetModel(**targets[0])
    assert t.ready_for_controlled_execution is False
    assert t.status in ("STATIC_ANALYZABLE", "EXECUTABLE_CANDIDATE", "COMPILATION_CANDIDATE")


def test_multipart_upload_and_zip(client):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("src/main.c", "int main(void){return 0;}\n")
        zf.writestr("src/util.h", "#pragma once\n")
    r = client.post("/api/v1/sources",
                    files={"file": ("bundle.zip", zip_buf.getvalue(), "application/zip")})
    assert r.status_code == 200
    body = r.json()
    assert body["file_count"] == 2 and body["rejected_count"] == 0
    targets = client.get(f"/api/v1/projects/{body['project_id']}/targets").json()
    kinds = {t["kind"] for t in targets}
    assert "c_translation_unit" in kinds and "c_multi_file" not in kinds


def test_malformed_zip_typed_error(client):
    r = client.post("/api/v1/sources",
                    files={"file": ("bad.zip", b"not-a-zip", "application/zip")})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "MALFORMED_ARCHIVE"


def test_paste_too_large_413(client):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "big.py", "content": "x" * 600_000})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_github_import_bad_url_structured_error(client):
    r = client.post("/api/v1/imports/github", json={"url": "http://github.com/o/r"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_URL"


def test_github_import_real_repo_online(client):
    """REAL network import — part of gate G3 (C-centric repo, SHA pinned)."""
    r = client.post("/api/v1/imports/github", json={"url": "https://github.com/antirez/kilo"})
    if r.status_code == 429:
        pytest.skip("GitHub unauthenticated rate limit exhausted; cached-snapshot import "
                    "provenance verified in docs/TEST_EVIDENCE/M1.md and M2 fallback tests")
    assert r.status_code == 200, r.text
    body = ImportManifestModel(**r.json())
    assert len(body.commit_sha) == 40
    assert body.canonical_owner == "antirez" and body.canonical_repo == "kilo"
    snap = client.get(f"/api/v1/projects/{body.project_id}/snapshots/{body.snapshot_id}").json()
    paths = {f["rel_path"] for f in snap["files"]}
    assert "kilo.c" in paths  # stable upstream filename
    targets = client.get(f"/api/v1/projects/{body.project_id}/targets").json()
    kilo = next(t for t in targets if t["primary_file"] == "kilo.c")
    assert kilo["status"] == "COMPILATION_CANDIDATE"
    assert any(r["code"] == "link-deps-unknown" and r["verified"] is False
               for r in kilo["reasons"])


def test_github_import_python_repo_online(client):
    """REAL network import — Python-centric repo with package structure."""
    r = client.post("/api/v1/imports/github", json={"url": "https://github.com/pallets/click"})
    if r.status_code == 429:
        pytest.skip("GitHub unauthenticated rate limit exhausted; M1 PASS evidence recorded "
                    "in docs/TEST_EVIDENCE/M1.md")
    assert r.status_code == 200, r.text
    body = ImportManifestModel(**r.json())
    assert len(body.commit_sha) == 40
    snap = client.get(f"/api/v1/projects/{body.project_id}/snapshots/{body.snapshot_id}").json()
    paths = {f["rel_path"] for f in snap["files"]}
    assert any(p.endswith("src/click/__init__.py") for p in paths)
    targets = client.get(f"/api/v1/projects/{body.project_id}/targets").json()
    statuses = {t["status"] for t in targets}
    assert "STATIC_ANALYZABLE" in statuses


def test_import_record_persisted_with_provenance(client):
    r = client.post("/api/v1/imports/github", json={"url": "https://github.com/antirez/kilo"})
    if r.status_code == 429:
        pytest.skip("GitHub unauthenticated rate limit exhausted (see M1 evidence)")
    body = r.json()
    rec = client.get(f"/api/v1/imports/{body['import_id']}").json()
    assert rec["policy_version"] == "m1.github.v1"
    assert rec["commit_sha"] == body["commit_sha"] and rec["retrieval_utc"]


def test_unknown_project_404_structured(client):
    r = client.get("/api/v1/projects/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_m0_regression_health_and_analyses(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    ids = {a["id"] for a in client.get("/api/v1/analyses").json()}
    assert {"m0-c", "m0-python"} <= ids
    cap = client.get("/api/v1/capabilities").json()
    assert cap["modes"]["pasted_execution"] == "BLOCKED"


def test_project_model_contract(client):
    r = client.post("/api/v1/sources", json={"kind": "paste", "language": "c",
                                             "filename": "t.c", "content": "int x;\n"})
    listing = client.get("/api/v1/projects").json()
    mine = next(p for p in listing if p["id"] == r.json()["project_id"])
    ProjectModel(id=mine["id"], name=mine["name"], created_utc=mine["created_utc"])
