import sys, tempfile, time, traceback
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
from app.services import execution
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "if __name__ == '__main__':\n    print('hello')\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "python", "filename": "h.py", "content": src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
eid = resp.json()["execution_id"]
runner = execution.get_execution_runner(c.app.state.store)
orig = runner._run
def traced(eid):
    try:
        orig(eid)
    except Exception:
        traceback.print_exc()
runner._run = traced
time.sleep(4)
j = c.get(f"/api/v1/executions/{eid}").json()
print("status:", j["status"], "| error:", j.get("error_code"))
