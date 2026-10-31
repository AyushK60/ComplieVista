import sys, tempfile, time
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "def outer():\n    def inner():\n        return 1\n    def inner():\n        return 2\n    return inner\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "python", "filename": "nested.py", "content": src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
job = c.post("/api/v1/analyses", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
aid = job["analysis_id"]
for _ in range(120):
    j = c.get(f"/api/v1/analyses/{aid}").json()
    if j["status"] not in ("RUNNING", "QUEUED"):
        break
    time.sleep(0.5)
bc = c.get(f"/api/v1/analyses/{aid}/stages/bytecode").json()
ids = sorted({i["code_object_id"] for i in bc["items"]})
print("status:", j["status"], "| counts:", bc["counts"])
print("ids:", ids)
