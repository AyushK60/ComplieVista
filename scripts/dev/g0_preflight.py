#!/usr/bin/env python3
"""G0 independent preflight checks (run inside WSL)."""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, "/mnt/e/ComplieVista/backend")
from fastapi.testclient import TestClient  # noqa: E402
from app.main import create_app  # noqa: E402
from app.store.db import Store  # noqa: E402

c = TestClient(create_app(store=Store(tempfile.mkdtemp(prefix="g0-"))))

# --- G0-CV03: no docker CLI on PATH -> typed BLOCKED, no 500 ---
env = dict(os.environ)
env["PATH"] = "/usr/bin:/bin"  # /usr/bin HAS docker on this machine; hide it:
import shutil  # noqa: E402
real_which = shutil.which
shutil.which = lambda name, **kw: None if name == "docker" else real_which(name, **kw)
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "python",
                                    "filename": "g0.py", "content": "x=1\n"}).json()
t = c.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
resp = c.post("/api/v1/analyses", json={"snapshot_id": r["snapshot_id"],
                                        "target_id": t["target_id"]})
print("G0-CV03:", resp.status_code, resp.json().get("status"), resp.json().get("error"))
shutil.which = real_which

# --- G0-CV01/02: real container analysis of a multi-function + switch C fixture ---
src = """#include <stdio.h>
static int classify(int v) {
    switch (v) {
    case 1: return 10;
    case 2: return 20;
    case 3: return 30;
    default: return 0;
    }
}
int main(void) {
    printf("%d\\n", classify(2));
    return 0;
}
"""
r = c.post("/api/v1/sources", json={"kind": "paste", "language": "c",
                                    "filename": "g0switch.c", "content": src}).json()
t = next(t for t in c.get(f"/api/v1/projects/{r['project_id']}/targets").json()
         if t["primary_file"] == "g0switch.c")
job = c.post("/api/v1/analyses", json={"snapshot_id": r["snapshot_id"],
                                       "target_id": t["target_id"]}).json()
aid = job["analysis_id"]
for _ in range(120):
    j = c.get(f"/api/v1/analyses/{aid}").json()
    if j["status"] in ("COMPLETED", "FAILED", "TIMEOUT", "BLOCKED"):
        break
    import time
    time.sleep(0.5)
print("G0 job status:", j["status"])
ast = c.get(f"/api/v1/analyses/{aid}/stages/ast").json()
roots = {n.get("name") for n in ast["items"] if n.get("parent") is None}
print("G0-CV01 primary roots:", sorted(n for n in roots if n in ("classify", "main")))
ir = c.get(f"/api/v1/analyses/{aid}/stages/ir_o0").json()
fn = next(f for f in ir["items"] if f["name"] == "classify")
entry = fn["blocks"][0]
print("G0-CV02 classify entry label:", entry["label"], "| successors:", entry["successors"])
# independent oracle: fresh host clang IR for the same source
ff = tempfile.NamedTemporaryFile("w", suffix=".c", delete=False)
ff.write(src)
ff.close()
oracle = subprocess.run(["clang", "-S", "-emit-llvm", "-g", "-O0", "-o", "-", ff.name],
                        capture_output=True, timeout=120).stdout.decode()
entry_succ = []
lines = oracle.splitlines()
i = 0
while i < len(lines):
    if re.match(r"^\s*switch\b", lines[i]) if (re := __import__("re")) else False:
        acc = lines[i].strip()
        while acc.count("[") - acc.count("]") > 0:
            i += 1
            acc += " " + lines[i].strip()
        entry_succ = __import__("re").findall(r"label\s+%([\w.$-]+)", acc)
        break
    i += 1
print("G0-CV02 oracle successors:", sorted(entry_succ))
inv = ir["invocation"]
print("G0-CV-sec image ref pinned:", inv.get("image_id", "").startswith("sha256:"),
      "| no docker.sock in argv:", "docker.sock" not in json.dumps(inv))
