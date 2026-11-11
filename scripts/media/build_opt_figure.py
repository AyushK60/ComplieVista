"""Builds frontend/src/data/optDiff.json from a REAL -O0/-O2 experiment fetched from the running
backend (demo C-02 by default). Per source line: asm instruction counts and the real instructions
at each level, taken from the compiler's debug-info line map. Nothing is invented; provenance
(tool, flags, step exit codes, artifact SHA-256) is copied from the experiment record.
Usage: python scripts/media/build_opt_figure.py [demo_id] [base_url]"""
import json
import sys
import time
import urllib.request

demo = sys.argv[1] if len(sys.argv) > 1 else "C-02"
base = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5173"


def get(p, post=False):
    req = urllib.request.Request(base + p, method="POST" if post else "GET")
    return json.load(urllib.request.urlopen(req, timeout=60))


exp = get(f"/api/v1/demos/{demo}/optimize", post=True)["experiment_id"]
for _ in range(60):
    e = get(f"/api/v1/experiments/{exp}")
    if e["status"] in ("COMPLETED", "FAILED"):
        break
    time.sleep(3)
assert e["status"] == "COMPLETED", e["status"]
lm = get(f"/api/v1/experiments/{exp}/linemap")
cmp = lm["compare_O0_O2"]
src = lm["source"].split("\n")
asm = {l: get(f"/api/v1/experiments/{exp}/artifacts/{l}/asm")["excerpt"].split("\n") for l in ("O0", "O2")}
stages = {s["stage"]: s for s in e["stages"]}
prov = {"tool": None, "experiment_id": exp, "demo": demo, "levels": {}}
for l in ("O0", "O2"):
    r = stages[l]["result"]
    prov["tool"] = r["tool"]["clang"]
    prov["levels"][l] = {"flags": r["flags"], "exit_codes": {k: v["exit_code"] for k, v in r["steps"].items()},
                         "asm_sha256": r["asm"]["sha256"], "ir_sha256": r["ir"]["sha256"]}
rows = []
for r in cmp["rows"]:
    if r["asm"][0] == 0 and r["asm"][1] == 0:
        continue
    ln = str(r["line"])
    pick = lambda lv: [asm[lv][i - 1].strip() for i in lm["levels"][lv]["by_source"].get(ln, {}).get("asm", [])][:8]
    rows.append({"line": r["line"], "text": src[r["line"] - 1], "asm": r["asm"], "ir": r["ir"],
                 "o0": pick("O0"), "o2": pick("O2")})
json.dump({"provenance": prov, "totals": cmp["totals"], "rows": rows},
          open("frontend/src/data/optDiff.json", "w", encoding="utf8"), indent=1)
print("wrote", len(rows), "rows from", exp)
