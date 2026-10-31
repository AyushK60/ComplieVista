"""Contract tests: M0 manifests must validate against the ADR-0002 typed schema."""
import json

import pytest
from pydantic import ValidationError

from app.contracts.models import AnalysisManifest, Availability, MappingConfidence, ObservationClass


@pytest.mark.parametrize("sub", ["c", "python"])
def test_manifest_validates(sub):
    data = json.loads(open(f"evidence/m0/{sub}/manifest.json").read())
    m = AnalysisManifest.model_validate(data)
    assert m.schema_version == "m0.v1"
    assert m.language.value == sub
    assert m.source_snapshot.files and m.source_snapshot.combined_sha256
    assert m.stages, "no stages recorded"
    for s in m.stages:
        assert s.availability in Availability
        assert s.observation_class in ObservationClass
        assert s.invocation.argv, "invocation argv must be recorded"


def test_language_stage_vocabularies_distinct():
    """Generic envelope names (tokens/ast/diagnostics) may repeat; language-specific
    representation stages must not leak across pipelines (ADR-0002)."""
    c = AnalysisManifest.model_validate(json.loads(open("evidence/m0/c/manifest.json").read()))
    py = AnalysisManifest.model_validate(json.loads(open("evidence/m0/python/manifest.json").read()))
    c_stages = {s.stage for s in c.stages}
    py_stages = {s.stage for s in py.stages}
    shared_generic = c_stages & py_stages
    assert shared_generic <= {"tokens", "ast", "diagnostics"}, \
        f"unexpected shared stage names: {shared_generic}"
    assert "ir" in c_stages and not ({"ir", "assembly", "object"} & py_stages)
    assert "bytecode" in py_stages and not ({"bytecode", "code_object"} & c_stages)


def test_invalid_enum_rejected():
    data = json.loads(open("evidence/m0/c/manifest.json").read())
    data["stages"][0]["availability"] = "MAGIC_ALL_GOOD"
    with pytest.raises(ValidationError):
        AnalysisManifest.model_validate(data)
