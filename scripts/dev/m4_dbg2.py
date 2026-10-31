import sys, tempfile
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "python",
                                    "filename": "x.py", "content": "v = 7\n"}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"],
                                          "target_id": t["target_id"]})
print(resp.status_code, resp.text[:300])
