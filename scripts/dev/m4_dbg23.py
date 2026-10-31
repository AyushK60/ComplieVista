import sys, tempfile, time
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "#include <stdio.h>\nstatic int adjust(int b, int l) {\n    return b > l ? l : b;\n}\nint main(void) {\n    printf(\"total=%d\n\", adjust(4, 2));\n    return 0;\n}\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "c", "filename": "calls.c", "content": src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
eid = resp.json()["execution_id"]
for _ in range(180):
    j = c.get(f"/api/v1/executions/{eid}").json()
    if j["status"] not in ("RUNNING", "QUEUED"): break
    time.sleep(0.5)
print("FULL:", json.dumps({k: j[k] for k in ("status", "error_code", "binary_sha256", "exit_code")}))
