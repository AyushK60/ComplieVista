"""Stage C: source/IR/asm line linking, checked against REAL clang-18 output.

Fixtures in tests/data/linemap were produced by `clang-18 -g -O0|-O2 -S [-emit-llvm]`
inside the pinned analyzer image from demo.c (see that file). The assertions are anchored
on facts about demo.c's own lines, not on the parser's output.
"""
from pathlib import Path

from app.services.linemap import build_linemap, compare_levels, parse_asm, parse_ir

D = Path(__file__).parent / "data" / "linemap"
SRC = (D / "demo.c").read_text()


def _map(level):
    return build_linemap(SRC, "demo.c", (D / f"ir_{level}.ll").read_text(),
                         (D / f"asm_{level}.s").read_text())


def test_source_fixture_lines():
    lines = SRC.splitlines()
    assert "return x * x;" in lines[3]            # line 4
    assert "total += square(i);" in lines[9]       # line 10
    assert "printf" in lines[16]                   # line 17


def test_o0_links_ir_and_asm_to_real_lines():
    m = _map("O0")
    assert m["has_debug_info"]
    by = m["by_source"]
    # the multiplication, the accumulation and the printf call all have IR and asm at -O0
    for line in (4, 10, 17):
        assert by[str(line)]["ir"], line
        assert by[str(line)]["asm"], line
    # every linked line is a real line of the file
    assert all(1 <= int(k) <= m["source_lines"] for k in by)


def test_o0_keeps_unused_local_o2_may_drop_it():
    # `int unused = 42;` is line 16: stored at -O0, dead at -O2 (no code attributed to it)
    assert _map("O0")["by_source"].get("16", {}).get("asm")
    assert not _map("O2")["by_source"].get("16", {}).get("asm")


def test_compare_reports_removed_lines():
    cmp = compare_levels(_map("O0"), _map("O2"))
    assert 16 in cmp["removed"]
    assert cmp["totals"]["asm"][0] > 0
    for r in cmp["rows"]:
        assert len(r["asm"]) == 2 and len(r["ir"]) == 2


def test_asm_mapping_only_covers_instructions():
    asm = (D / "asm_O0.s").read_text().splitlines()
    mp = parse_asm("\n".join(asm), "demo.c")
    assert mp
    for ln in mp:
        text = asm[ln - 1].strip()
        assert not text.startswith((".", "#")) and not text.endswith(":"), text


def test_ir_mapping_only_covers_instructions_with_dbg():
    ir = (D / "ir_O0.ll").read_text().splitlines()
    mp = parse_ir("\n".join(ir))
    assert mp
    for ln in mp:
        assert "!dbg" in ir[ln - 1]


def test_no_debug_info_is_reported_not_faked():
    m = build_linemap(SRC, "demo.c", "define i32 @f() {\n  ret i32 0\n}\n",
                      "f:\n\txorl %eax, %eax\n\tretq\n")
    assert m["has_debug_info"] is False
    assert m["by_source"] == {}


def test_foreign_file_locs_are_not_attributed_to_primary():
    asm = ('\t.file\t0 "/" "/work/demo.c"\n\t.file\t1 "/usr/include" "stdio.h"\n'
           "f:\n\t.loc\t1 99 1\n\tnop\n\t.loc\t0 4 1\n\tret\n")
    assert parse_asm(asm, "demo.c") == {7: 4}


# ---------------- API: real container build -> linemap ----------------
import time  # noqa: E402


def test_linemap_endpoint_real_build(client):
    r = client.post("/api/v1/sources", json={"kind": "paste", "language": "c",
                                              "filename": "demo.c", "content": SRC}).json()
    tgt = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]["target_id"]
    eid = client.post("/api/v1/experiments", json={
        "kind": "opt", "snapshot_id": r["snapshot_id"], "target_id": tgt}).json()["experiment_id"]
    for _ in range(300):
        j = client.get(f"/api/v1/experiments/{eid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            break
        time.sleep(0.5)
    assert j["status"] == "COMPLETED", j.get("error_code")
    res = client.get(f"/api/v1/experiments/{eid}/linemap")
    assert res.status_code == 200, res.text[:200]
    body = res.json()
    assert set(body["levels"]) == {"O0", "O1", "O2"}
    assert all(lv["has_debug_info"] for lv in body["levels"].values())
    assert 16 in body["compare_O0_O2"]["removed"]          # the dead local (line 16)
    assert client.get("/api/v1/experiments/nope/linemap").status_code == 404
