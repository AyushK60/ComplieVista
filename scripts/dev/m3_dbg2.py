import sys, tempfile, time
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "static int classify(int v) {\n    switch (v) {\n    case 1: return 10;\n    case 2: return 20;\n    case 3: return 30;\n    default: return 0;\n    }\n}\nint main(void) { return classify(2); }\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "c", "filename": "sw.c", "content": src}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
job = c.post("/api/v1/analyses", json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
aid = job["analysis_id"]
for _ in range(120):
    j = c.get(f"/api/v1/analyses/{aid}").json()
    if j["status"] not in ("RUNNING", "QUEUED"): break
    time.sleep(0.5)
g = c.get(f"/api/v1/analyses/{aid}/stages/ast/graph").json()
from collections import Counter
parents = Counter(e["target"] for e in g["edges"] if e["kind"] == "containment")
dupes = {k: v for k, v in parents.items() if v > 1}
for k in dupes:
    node = next(n for n in g["nodes"] if n["id"] == k)
    print("DUPE target:", node["kind"], node["name"], node.get("line"))
    for e in g["edges"]:
        if e["target"] == k and e["kind"] == "containment":
            src_node = next(n for n in g["nodes"] if n["id"] == e["source"])
            print("   from:", src_node["kind"], src_node["name"], src_node.get("line"))
