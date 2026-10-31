import sys, tempfile
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
GUARDED_SPIN = "if __name__ == '__main__':\n    while True:\n        pass\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "python",
                                    "filename": "spin.py", "content": GUARDED_SPIN}).json()
targets = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()
print("targets:", [(t["target_id"][:12], t["status"]) for t in targets])
t = targets[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"],
                                          "target_id": t["target_id"]})
print("POST:", resp.status_code, resp.text[:200])
