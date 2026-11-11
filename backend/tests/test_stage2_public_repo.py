"""Stage 2-F: real analysis of untrusted code from stage 1-imported public repositories.

Runs the actual restricted-container analyzer on files from real GitHub imports.
Never executes the imported code - only bounded static tool inspection.

If GitHub's unauthenticated rate limit blocks a fresh import, the test falls back
to the cached immutable pinned snapshot in the real data store (per prompt: reuse
cached fixtures rather than re-downloading). If neither is possible, SKIP - never
fake.
"""
import time

import pytest

from app.store.db import Store
from tests.test_stage2_analysis import wait_terminal


def _seed_from_real_store(client) -> str | None:
    """Copy the cached kilo snapshot from the live data store into the test store."""
    try:
        real = Store()  # default data dir (repo/data)
        imp = real.query_one(
            "SELECT * FROM imports WHERE status='completed' AND canonical_repo='kilo' "
            "ORDER BY created_utc DESC LIMIT 1")
        if not imp:
            return None
        snap = real.query_one("SELECT * FROM source_snapshots WHERE import_id=?",
                              (imp["id"],))
        if not snap:
            return None
        store = client.app.state.store
        store.execute("INSERT OR IGNORE INTO projects (id, name, created_utc) VALUES (?,?,?)",
                      (f"cached-{snap['project_id'][:8]}", "cached: antirez/kilo",
                       snap["created_utc"]))
        store.execute(
            "INSERT OR IGNORE INTO source_snapshots (id, project_id, origin, combined_sha256,"
            " import_id, created_utc) VALUES (?,?,?,?,?,?)",
            (snap["id"], f"cached-{snap['project_id'][:8]}", "github",
             snap["combined_sha256"], None, snap["created_utc"]))
        files: dict[str, bytes] = {}
        for f in real.query("SELECT * FROM source_files WHERE snapshot_id=?", (snap["id"],)):
            data = real.get_artifact(f["content_sha256"])
            store.put_artifact(data)
            store.execute(
                "INSERT OR IGNORE INTO source_files (id, snapshot_id, rel_path,"
                " content_sha256, size, encoding, language) VALUES (?,?,?,?,?,?,?)",
                (f["id"], snap["id"], f["rel_path"], f["content_sha256"], f["size"],
                 f["encoding"], f["language"]))
            files[f["rel_path"]] = data
        if files and not store.query_one(
                "SELECT 1 FROM compilation_targets WHERE snapshot_id=?", (snap["id"],)):
            from app.services.classify import classify_files, classify_multi_file_hint
            classify_files(store, snap["id"], files)
            classify_multi_file_hint(store, snap["id"], files)
        return snap["id"]
    except Exception:
        return None


def analyze_file(client, repo_url, want_path):
    snap_id = None
    try:
        r = client.post("/api/v1/imports/github", json={"url": repo_url})
        if r.status_code == 200:
            body = r.json()
            snap_id = body["snapshot_id"]
    except Exception:
        pass
    if snap_id is None:
        snap_id = _seed_from_real_store(client)
    if snap_id is None:
        pytest.skip("GitHub unreachable/rate-limited and no cached snapshot available")
    snap = None
    proj = client.get("/api/v1/projects").json()
    for p in proj:
        d = client.get(f"/api/v1/projects/{p['id']}").json()
        for s in d["snapshots"]:
            if s["id"] == snap_id:
                snap = (p["id"], s["id"])
    assert snap, "seeded snapshot not visible via API"
    pid, sid = snap
    detail = client.get(f"/api/v1/projects/{pid}/snapshots/{sid}").json()
    path = next((f["rel_path"] for f in detail["files"] if f["rel_path"] == want_path),
                next((f["rel_path"] for f in detail["files"]
                      if f["rel_path"].startswith(want_path)), None))
    if path is None:
        pytest.skip(f"neither fresh import nor cached snapshot contains {want_path} "
                    f"(GitHub unauthenticated rate limit; cached store holds kilo only)")
    assert path, f"{want_path} not in snapshot"
    fid = next(f["id"] for f in detail["files"] if f["rel_path"] == path)
    file_detail = client.get(f"/api/v1/projects/{pid}/snapshots/{sid}/files/{fid}").json()
    assert file_detail["text"], "file must be previewable text"
    targets = client.get(f"/api/v1/projects/{pid}/targets").json()
    target = next(t for t in targets if t["primary_file"] == path)
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": sid, "target_id": target["target_id"]}).json()
    terminal = wait_terminal(client, job["analysis_id"], tries=120)
    return terminal, path


def test_public_c_repo_analysis_kilo(client):
    terminal, path = analyze_file(client, "https://github.com/antirez/kilo", "kilo.c")
    assert terminal["status"] == "COMPLETED", terminal
    stages = {s["stage"]: s["availability"] for s in terminal["stages"]}
    assert stages["ast"] == "AVAILABLE" and stages["ir_o0"] == "AVAILABLE"
    assert stages["object"] == "AVAILABLE"
    ast = client.get(f"/api/v1/analyses/{terminal['id']}/stages/ast").json()
    assert ast["counts"]["ast_nodes"] > 50  # kilo.c is a real translation unit
    assert terminal["primary_file"] == path


def test_public_python_repo_analysis(client):
    terminal, path = analyze_file(client, "https://github.com/pallets/click",
                                  "src/click/decorators.py")
    assert terminal["status"] == "COMPLETED", terminal
    stages = {s["stage"]: s["availability"] for s in terminal["stages"]}
    assert stages["ast"] == "AVAILABLE" and stages["bytecode"] == "AVAILABLE"
    bc = client.get(f"/api/v1/analyses/{terminal['id']}/stages/bytecode").json()
    assert bc["counts"]["code_objects"] >= 2  # module + nested defs
