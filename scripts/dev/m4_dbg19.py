import sys, tempfile
sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.db import Store
c = TestClient(create_app(store=Store(tempfile.mkdtemp())))
src = "if __name__ == '__main__':\n    for i in range(5):\n        print(i)\n"
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "python",
                                    "filename": "pg.py", "content": src}).json()
ts = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()
print([(t["target_id"][:8], t["status"], t["primary_file"]) for t in ts])
snap = c.get(f"/api/v1/projects/{r['project_id']}").json()
print("snapshots:", len(snap["snapshots"]))
