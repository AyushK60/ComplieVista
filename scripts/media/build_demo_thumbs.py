"""Builds frontend/src/data/demoThumbs.json: one REAL frame per demo, taken from the live analysis of
that program through the running backend (tokens and AST stages, plus the snapshot's own source).
Nothing is hand-written. Requires the backend on 127.0.0.1:8123 (Start.cmd)."""
import json
import re
import urllib.request

B = "http://127.0.0.1:8123/api/v1"
TRIVIA = {"NEWLINE", "NL", "INDENT", "DEDENT", "ENDMARKER", "ENCODING", "COMMENT"}


def get(p):
    return json.load(urllib.request.urlopen(B + p, timeout=60))


def post(p):
    return json.load(urllib.request.urlopen(urllib.request.Request(B + p, method="POST"), timeout=180))


cat = get("/demos")["demos"]
out = {}
for d in cat:
    did = d["id"]
    lang = "python" if (did.startswith("PY-") or did.endswith("-PY")) else "c"
    r = post(f"/demos/{did}/analyze")
    a = r["analysis_id"]
    snap = get(f"/projects/demo-library/snapshots/{r['snapshot_id']}")
    prim = d["primary_file"].split("/")[-1]
    f = next((x for x in snap["files"] if x["rel_path"].endswith(prim)), snap["files"][0])
    text = get(f"/projects/demo-library/snapshots/{r['snapshot_id']}/files/{f['id']}")["text"] or ""
    lines = text.split("\n")
    tok = get(f"/analyses/{a}/stages/tokens")
    ast = get(f"/analyses/{a}/stages/ast")

    def own(t):
        return lang == "python" or (t.get("file") or "").endswith(prim)

    toks = [t for t in tok["items"] if own(t) and t["kind"] not in TRIVIA and "\n" not in t["text"]]
    # the first function signature is the frame's subject
    sig = next((i for i, l in enumerate(lines) if re.match(r"\s*(def |static |int |void |double |float |char |unsigned |long )", l) and "(" in l and not l.strip().startswith("#")), 0)
    excerpt = [l.rstrip() for l in lines[sig:sig + 6]]
    first = [t for t in toks if t["line"] == sig + 1][:9]
    nodes = {n["id"]: n for n in ast["items"]}
    fnkind = "FunctionDef" if lang == "python" else "FunctionDecl"
    fn = next((n for n in ast["items"] if n["kind"] == fnkind and n.get("children")), None)
    tree = []
    if fn:
        tree.append({"kind": fn["kind"], "name": fn.get("name"), "depth": 0})
        for cid in fn["children"][:5]:
            c = nodes[cid]
            tree.append({"kind": c["kind"], "name": c.get("name"), "depth": 1})
    out[did] = {
        "lang": lang,
        "excerpt": excerpt,
        "excerpt_from": sig + 1,
        "tokens": [{"kind": t["kind"], "text": t["text"]} for t in first],
        "tree": tree,
        "counts": {"tokens": (len(toks) if not tok.get("truncated") else None) if lang == "python" else tok["counts"].get("tokens_primary_file"), "ast_nodes": len(ast["items"]) if not ast.get("truncated") else None},
        "prov": {"analysis_id": a, "tokens_sha256": tok.get("raw_artifact_sha256"), "ast_sha256": ast.get("raw_artifact_sha256")},
    }
    print(did, len(toks), len(ast["items"]), len(tree))
json.dump({"generated_from": "live backend analysis (tokens and ast stages) of each demo", "demos": out}, open("frontend/src/data/demoThumbs.json", "w"), indent=1)
