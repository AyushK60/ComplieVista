import sys, tempfile, time, traceback
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from app.store.db import Store
from app.services.execution import get_execution_runner
from fastapi.testclient import TestClient
from app.main import create_app
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "#include <stdio.h>\nstatic int adjust(int b, int l){ return b > l ? l : b; }\nint main(void) { return adjust(4, 2); }\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "c", "filename": "calls.c", "content": src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
eid = resp.json()["execution_id"]
runner = get_execution_runner(c.app.state.store)
try:
    runner._run(eid)
except Exception:
    traceback.print_exc()
j = c.get(f"/api/v1/executions/{eid}").json()
print("status:", j["status"], "error:", j.get("error_code"))
