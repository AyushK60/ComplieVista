"""Builds frontend/src/data/figures.json from RECORDED tool output only: evidence/m0 plus one real
sandbox run of PY-01 fetched from the running backend. Nothing is invented; the only derived field
is the assembly -> source alignment, which is labelled DERIVED in the data."""
import hashlib
import json
import re
import urllib.request

E = "evidence/m0"
out = {}

# ---- C: AST, IR, asm for scale_and_adjust (demos/m0/c_fixture.c) ----
csrc = open("demos/m0/c_fixture.c", encoding="utf8").read().split("\n")
manifest = json.load(open(f"{E}/c/manifest.json"))
c_sha = manifest["source_snapshot"]["combined_sha256"]
ast = json.load(open(f"{E}/c/ast/ast.json"))
fn = [c for c in ast["inner"] if c.get("name") == "scale_and_adjust"][0]
last = [7]


def conv(n):
    b = (n.get("range") or {}).get("begin") or {}
    b = b.get("expansionLoc", b)
    if "line" in b:
        last[0] = b["line"]
    node = {"kind": n["kind"], "line": last[0]}
    if n.get("name"):
        node["name"] = n["name"]
    if n.get("opcode"):
        node["name"] = n["opcode"]
    if n["kind"] == "IntegerLiteral":
        node["name"] = str(n.get("value"))
    if n["kind"] == "DeclRefExpr":
        node["name"] = (n.get("referencedDecl") or {}).get("name")
    if n["kind"] == "ImplicitCastExpr":
        node["name"] = n.get("castKind")
        node["implicit"] = True
    kids = [conv(c) for c in n.get("inner", []) if isinstance(c, dict)]
    if kids:
        node["children"] = kids
    return node


out["ast"] = {
    "provenance": {
        "tool": manifest["tools"]["clang"],
        "invocation": "clang -Xclang -ast-dump=json (recorded in evidence/m0/c/ast/ast.json)",
        "source": "demos/m0/c_fixture.c",
        "source_sha256": c_sha,
    },
    "source": [{"n": i + 1, "text": csrc[i]} for i in range(6, 13)],
    "tree": conv(fn),
}

ll = open(f"{E}/c/ir/ir_O0.ll", encoding="utf8").read()
loc = {m.group(1): int(m.group(2)) for m in re.finditer(r"^!(\d+) = !DILocation\(line: (\d+)", ll, re.M)}
fnll = re.search(r"define [^\n]*@scale_and_adjust.*?\n}\n", ll, re.S).group(0).split("\n")
ir = []
for l in fnll:
    if not l.strip() or l.strip() == "}" or "llvm.dbg.declare" in l:
        continue
    m = re.search(r"!dbg !(\d+)", l)
    text = re.sub(r",? ?!dbg !\d+", "", l)
    text = re.sub(r"\s*#\d+ *!dbg.*$", "", text).rstrip()
    ir.append({"text": text, "line": loc.get(m.group(1)) if m else None})

asm_raw = open(f"{E}/c/assembly/fixture_O0.s", encoding="utf8").read().split("\n")
a0 = next(i for i, l in enumerate(asm_raw) if l.startswith("scale_and_adjust:"))
a1 = next(i for i, l in enumerate(asm_raw) if i > a0 and l.startswith(".Lfunc_end1"))
asm = []
seen_cmp = False
in_else = False
for l in asm_raw[a0 + 1:a1]:
    t = l.split("#")[0].rstrip() if not l.lstrip().startswith("#") else ""
    s = t.strip()
    if not s or s.startswith(".cfi"):
        continue
    ln = None
    if s in ("pushq\t%rbp", "movq\t%rsp, %rbp", "movl\t%edi, -8(%rbp)", "movl\t%esi, -12(%rbp)"):
        ln = 7
    elif s.startswith("imull") or s == "movl\t%eax, -16(%rbp)":
        ln = 8
    elif s.startswith("cmpl") or s.startswith("jle"):
        ln = 9
        seen_cmp = True
    elif s == "movl\t-16(%rbp), %eax" and not seen_cmp:
        ln = 9
    elif s.startswith(".LBB1_2"):
        in_else = True
        ln = 12
    elif s == "movl\t-12(%rbp), %eax" or (s == "movl\t%eax, -4(%rbp)" and not in_else) or s.startswith("jmp"):
        ln = 10
    elif in_else and s in ("movl\t-16(%rbp), %eax", "movl\t%eax, -4(%rbp)"):
        ln = 12
    elif s.startswith(".LBB1_3") or s.startswith("movl\t-4(%rbp)") or s.startswith("popq") or s.startswith("retq"):
        ln = 13
    asm.append({"text": s.replace("\t", "  "), "line": ln})
out["c_lower"] = {
    "provenance": {
        "tool": manifest["tools"]["clang"],
        "invocations": ["clang -S -emit-llvm -g -O0 (evidence/m0/c/ir/ir_O0.ll)", "clang -S -O0 (evidence/m0/c/assembly/fixture_O0.s)"],
        "source_sha256": c_sha,
        "ir_link": "EXACT: from the compiler's own !DILocation entries",
        "asm_link": "DERIVED: this recording has no line table for the assembly; instructions are aligned to the IR statements",
    },
    "source": [{"n": i + 1, "text": csrc[i]} for i in range(6, 13)],
    "ir": ir,
    "asm": asm,
}

# ---- Python: dis for scale_and_adjust (demos/m0/py_fixture.py) ----
dis = open(f"{E}/python/bytecode/dis.txt", encoding="utf8").read()
sec = re.search(r"=== code object: scale_and_adjust ===\n(.*?)(?=\n=== code object|\Z)", dis, re.S).group(1).split("\n")
pysrc = open("demos/m0/py_fixture.py", encoding="utf8").read().split("\n")
rows = []
curline = None
for l in sec:
    if not l.strip():
        continue
    m = re.match(r"\s*(\d+)?\s+(?:>>)?\s*(\d+)\s+(\w+)\s*(.*)$", l)
    if not m:
        continue
    if m.group(1):
        curline = int(m.group(1))
    rows.append({"line": curline, "offset": int(m.group(2)), "op": m.group(3), "arg": m.group(4).strip()})
out["py_lower"] = {
    "provenance": {
        "tool": "CPython 3.12",
        "invocation": "dis.dis (recorded in evidence/m0/python/bytecode/dis.txt)",
        "source": "demos/m0/py_fixture.py",
        "link": "EXACT: the line column of dis itself",
    },
    "source": [{"n": i + 1, "text": pysrc[i]} for i in range(9, 14)],
    "dis": rows,
}

# ---- recorded sandbox run: PY-01 ----
base = "http://127.0.0.1:8123/api/v1"


def get(p):
    return json.load(urllib.request.urlopen(base + p))


run = json.load(urllib.request.urlopen(urllib.request.Request(base + "/demos/PY-01/run", method="POST"), timeout=120))
ex = get(f"/executions/{run['execution_id']}")
ev = get(f"/executions/{run['execution_id']}/events?after=0&limit=200")["events"]
src = open("sandbox/fixtures/demos/PY-01.py", encoding="utf8").read().split("\n")
steps = []
for e in ev:
    p = e["payload"]
    if e["kind"] == "exit":
        continue
    s = {"kind": e["kind"], "fn": p.get("fn"), "line": p.get("line"), "depth": p.get("depth")}
    if e["kind"] == "call":
        s["locals"] = {k: v.get("repr") for k, v in (p.get("locals") or {}).items() if not k.startswith("__")}
    if e["kind"] == "return":
        s["ret"] = (p.get("arg") or {}).get("repr")
    steps.append(s)
out["run"] = {
    "provenance": {
        "tool": "CPython 3.12 sys.settrace in the runtime container",
        "demo": "PY-01",
        "execution_id": run["execution_id"],
        "exit_code": run["exit_code"],
        "source_sha256": ex["source_combined_sha256"],
        "trace_sha256": ex["trace_sha256"],
        "stdout_sha256": ex["stdout_sha256"],
        "image_id": ex["image_id"],
        "events": ex["events_count"],
    },
    "source": [{"n": i + 1, "text": src[i]} for i in range(len(src))],
    "steps": steps,
    "stdout": run["stdout"],
}
json.dump(out, open("frontend/src/data/figures.json", "w"), indent=1)
print("ok", len(ir), len(asm), len(rows), len(steps), len(src))
