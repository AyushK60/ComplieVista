"""The paged /events endpoint must be served from an index, not a table scan.

Regression: without an index on (execution_id, seq) every request scanned all
recorded events (~1.3 s each with a few thousand rows), so a 2.3k-event trace
took 10-15 s to load in the UI.
"""
from __future__ import annotations

from app.store.db import Store


def _plan(store: Store, sql: str, params: tuple) -> str:
    rows = store.query("EXPLAIN QUERY PLAN " + sql, params)
    return " | ".join(str(r["detail"]) for r in rows)


def test_events_query_uses_index(store: Store) -> None:
    plan = _plan(
        store,
        "SELECT seq, kind, payload_json, sha256 FROM execution_events"
        " WHERE execution_id=? AND seq>? ORDER BY seq LIMIT ?",
        ("x", 0, 500),
    )
    assert "idx_exec_events_exec_seq" in plan, plan
    assert "SCAN" not in plan.replace("SEARCH", ""), plan


def test_index_creation_is_idempotent(tmp_path) -> None:
    data = tmp_path / "data"
    Store(data_dir=data)
    Store(data_dir=data)  # reopening an upgraded store must not fail
