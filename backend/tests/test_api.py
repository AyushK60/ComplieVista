"""API contract tests for the M0 surface (docs/API_CONTRACTS.md)."""
import json
import tempfile

from fastapi.testclient import TestClient

from app.main import create_app
from app.store.db import Store

client = TestClient(create_app(store=Store(tempfile.mkdtemp(prefix="cv-m0-api-"))))


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # additive schema bumps (ADR-0002/0005): track the application constant
    from app.core.config import SCHEMA_VERSION
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["python_version"].startswith("3.12")


def test_capabilities_honest_modes():
    r = client.get("/api/v1/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["tools"]["clang"]["available"] is True
    assert "18.1.3" in body["tools"]["clang"]["version"]
    assert body["modes"]["pasted_execution"] == "PARTIAL"  # M4QA-05: honest since the M4 gate passed
    assert body["modes"]["curated_execution"] == "PARTIAL"


def test_analyses_list_two_real_pipelines():
    r = client.get("/api/v1/analyses")
    assert r.status_code == 200
    items = {a["id"]: a for a in r.json()}
    assert set(items) == {"m0-c", "m0-python"}
    assert items["m0-c"]["language"] == "c" and items["m0-python"]["language"] == "python"


def test_analysis_detail():
    r = client.get("/api/v1/analyses/m0-c")
    assert r.status_code == 200
    body = r.json()
    stages = {s["stage"] for s in body["stages"]}
    assert {"preprocess", "tokens", "ast", "ir", "assembly", "object"} <= stages
    assert body["source_snapshot"]["combined_sha256"]


def test_stage_tokens_bounded_and_exact():
    r = client.get("/api/v1/analyses/m0-python/stages/tokens")
    assert r.status_code == 200
    body = r.json()
    assert body["availability"] == "AVAILABLE"
    assert body["observation_class"] == "TOOL_OUTPUT"
    assert body["items_total"] == body["counts"]["tokens"]
    assert len(body["items"]) <= 500
    if body["items_total"] > 500:
        assert body["truncated"] is True
    assert body["items"][0]["mapping_confidence"] in ("EXACT", "DERIVED", "UNAVAILABLE")


def test_stage_ir_text_excerpt():
    r = client.get("/api/v1/analyses/m0-c/stages/ir")
    assert r.status_code == 200
    body = r.json()
    assert body["artifact"]["sha256"]
    assert body["counts"]["functions"] == 2


def test_unknown_analysis_and_stage_404_structured():
    r = client.get("/api/v1/analyses/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    r = client.get("/api/v1/analyses/m0-c/stages/not_a_stage")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_no_raw_absolute_paths_in_responses():
    for url in ("/api/v1/analyses", "/api/v1/analyses/m0-python/stages/tokens"):
        body = json.dumps(client.get(url).json())
        assert "/mnt/e" not in body and "C:\\" not in body
