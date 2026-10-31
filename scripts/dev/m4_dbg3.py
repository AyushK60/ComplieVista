import sys, tempfile, time
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "#include <stdio.h>\nstatic int adjust(int base, int limit) {\n    if (base > limit) { return limit; }\n    return base;\n}\nint main(void) {\n    int total = adjust(4, 2);\n    printf(\"total=%d\n\", total);\n    return 0;\n}\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "c", "filename": "calls.c", "content": src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/executions", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
print("POST:", resp.status_code, resp.text[:200])
eid = resp.json()["execution_id"]
for _ in range(180):
    j = c.get(f"/api/v1/executions/{eid}").json()
    if j["status"] not in ("RUNNING", "QUEUED"): break
    time.sleep(0.5)
print("status:", j["status"], "| error:", j.get("error_code"), "| exit:", j.get("exit_code"))
evs = c.get(f"/api/v1/executions/{eid}/events?limit=10").json()
print("events:", [(e["kind"], e["payload"].get("fn") or e["payload"].get("exc")) for e in evs["events"]][:8])
