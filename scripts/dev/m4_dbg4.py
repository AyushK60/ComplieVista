import sys, tempfile, time, traceback
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from app.store.db import Store
from app.services.execution import get_execution_runner
from fastapi.testclient import TestClient
from app.main import create_app
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "#include <stdio.h>\nint main(void) { return 0; }\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "c", "filename": "m.c", "content": src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
eid = resp.json()["execution_id"]
runner = get_execution_runner(c.app.state.store)
orig = runner._run
def traced(eid):
    try:
        orig(eid)
    except Exception:
        traceback.print_exc()
runner._run = traced
for _ in range(120):
    j = c.get(f"/api/v1/executions/{eid}").json()
    if j["status"] not in ("RUNNING", "QUEUED"): break
    time.sleep(0.5)
print("done")
