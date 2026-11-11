"""Stage 8 recovery regression: the C tokens stage must not let included-header
tokens drown the user's own file when the item cap applies. clang -dump-tokens
emits header tokens first (the #include is at the top of the TU), so a capped
stage could previously contain ONLY stdio.h tokens and none of the user's
program. Same policy as the AST walk (CV-01): primary file first, headers
counted, positions never rewritten."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.normalize import ingest_stage_records
from app.store.db import Store, new_id, now_utc


def _tok_line(kind: str, text: str, file: str, line: int, col: int) -> str:
    return f"{kind} '{text}'\t\tLoc=<{file}:{line}:{col}>"


def test_c_tokens_cap_prioritizes_primary_file(tmp_path):
    store = Store(data_dir=tmp_path / "data")
    aid = new_id()
    store.execute(
        "INSERT INTO analyses (id, snapshot_id, target_id, language, primary_file, status,"
        " fingerprint, source_combined_sha256, error_code, created_utc)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (aid, "snap-x", "tgt-x", "c", "demo.c", "COMPLETED", "fp", "sha", None, now_utc()))

    dump = "\n".join(
        [_tok_line("keyword", "int", "stdio.h", i, 1) for i in range(1, 600)]
        + [_tok_line("identifier", "swap", "demo.c", 6, 1),
           _tok_line("keyword", "int", "demo.c", 6, 6)])
    out = tmp_path / "out"
    out.mkdir()
    (out / "tokens.txt").write_text(dump + "\n", "utf-8")
    (out / "manifest.json").write_text(json.dumps({"stages": [
        {"stage": "tokens", "exit_code": 0, "stderr": {"file": "tokens.txt"}}]}), "utf-8")

    assert ingest_stage_records(store, aid, out, "c", primary_file="demo.c") == 1
    row = store.query_one(
        "SELECT items_json, counts_json, truncated FROM analysis_stages"
        " WHERE analysis_id=? AND stage='tokens'", (aid,))
    items = json.loads(row["items_json"])
    assert [t["text"] for t in items[:2]] == ["swap", "int"]
    assert all(Path(t["file"]).name == "demo.c" for t in items[:2])
    assert json.loads(row["counts_json"])["tokens"] == 601
    assert row["truncated"] == 1
    # header tokens are still served after the primary file's tokens
    assert any(Path(t["file"]).name == "stdio.h" for t in items)


def test_c_tokens_survive_a_header_heavy_dump(tmp_path):
    """Regression: the dump parser used to stop at 8000 tokens. Headers come first, so a program
    including stdio.h and stdlib.h (C-04) lost every one of its own tokens. The parser now reads the
    whole dump; own-file tokens are served first and counted exactly."""
    store = Store(data_dir=tmp_path / "data")
    aid = new_id()
    store.execute(
        "INSERT INTO analyses (id, snapshot_id, target_id, language, primary_file, status,"
        " fingerprint, source_combined_sha256, error_code, created_utc)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (aid, "snap-y", "tgt-y", "c", "heavy.c", "COMPLETED", "fp2", "sha", None, now_utc()))
    dump = "\n".join(
        [_tok_line("keyword", "int", "stdlib.h", 1 + i, 1) for i in range(9000)]
        + [_tok_line("identifier", "main", "heavy.c", 14, 5),
           _tok_line("l_paren", "(", "heavy.c", 14, 9)])
    out = tmp_path / "out2"
    out.mkdir()
    (out / "tokens.txt").write_text(dump + "\n", "utf-8")
    (out / "manifest.json").write_text(json.dumps({"stages": [
        {"stage": "tokens", "exit_code": 0, "stderr": {"file": "tokens.txt"}}]}), "utf-8")

    assert ingest_stage_records(store, aid, out, "c", primary_file="heavy.c") == 1
    row = store.query_one(
        "SELECT items_json, counts_json FROM analysis_stages WHERE analysis_id=? AND stage='tokens'", (aid,))
    items = json.loads(row["items_json"])
    counts = json.loads(row["counts_json"])
    assert [t["text"] for t in items[:2]] == ["main", "("]
    assert counts["tokens"] == 9002
    assert counts["tokens_primary_file"] == 2
