import sys, tempfile, time
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
from app.services import execution
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
orig = execution.run_capped
def spy(argv, timeout):
    print("ARGV:", " ".join(argv)[:400])
    r = orig(argv, timeout)
    print("RC:", r["exit_code"], "| killed:", r["killed"], "| stderr:", r["stderr"].decode("utf-8","replace")[:300])
    return r
execution.run_capped = spy
src = "static int adjust(int b, int l){ return b > l ? l : b; }\nint main(void) { return adjust(4, 2); }\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "c", "filename": "calls.c", "content": "#include <stdio.h>\n" + src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
eid = resp.json()["execution_id"]
for _ in range(180):
    j = c.get(f"/api/v1/executions/{eid}").json()
    if j["status"] not in ("RUNNING", "QUEUED"): break
    time.sleep(0.5)
print("status:", j["status"], "| error:", j.get("error_code"))
