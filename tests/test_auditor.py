import json

from sherpa.auditor import audit, audit_consistency, audit_grounding, audit_schema
from sherpa.schema import AuditErrorType
from tests.fixtures import (
    BAD_GROUNDING_AND_DUPLICATE_JSON,
    BAD_GROUNDING_JSON,
    BAD_SCHEMA_JSON,
    DUPLICATE_FINDINGS_JSON,
    GOOD_JSON,
    MOCK_CONTEXT,
    WIKI_ONLY_CONTEXT,
)


class TestAuditSchema:
    def test_passes_valid_json(self):
        errors, output = audit_schema(GOOD_JSON)
        assert errors == []
        assert output is not None
        assert output.query == "quantum computing"

    def test_catches_invalid_json(self):
        errors, output = audit_schema("not json at all {{{")
        assert len(errors) == 1
        assert errors[0].error_type == AuditErrorType.SCHEMA
        assert output is None

    def test_catches_missing_fields(self):
        errors, output = audit_schema(BAD_SCHEMA_JSON)
        assert any(e.error_type == AuditErrorType.SCHEMA for e in errors)
        assert output is None

    def test_catches_empty_findings(self):
        data = json.loads(GOOD_JSON)
        data["findings"] = []
        errors, output = audit_schema(json.dumps(data))
        assert any(e.error_type == AuditErrorType.SCHEMA for e in errors)

    def test_catches_confidence_out_of_range(self):
        data = json.loads(GOOD_JSON)
        data["findings"][0]["confidence"] = 1.5
        errors, output = audit_schema(json.dumps(data))
        assert any(e.error_type == AuditErrorType.SCHEMA for e in errors)


class TestAuditGrounding:
    def test_passes_real_snippet(self):
        _, output = audit_schema(GOOD_JSON)
        errors = audit_grounding(output, MOCK_CONTEXT)
        assert errors == []

    def test_catches_fabricated_snippet(self):
        _, output = audit_schema(BAD_GROUNDING_JSON)
        errors = audit_grounding(output, MOCK_CONTEXT)
        assert len(errors) > 0
        assert all(e.error_type == AuditErrorType.GROUNDING for e in errors)


class TestAuditConsistency:
    def test_catches_duplicate_findings(self):
        _, output = audit_schema(DUPLICATE_FINDINGS_JSON)
        errors = audit_consistency(output, MOCK_CONTEXT)
        assert any(e.error_type == AuditErrorType.CONSISTENCY for e in errors)
        assert any("Duplicate" in e.message for e in errors)

    def test_catches_invalid_source_type(self):
        _, output = audit_schema(GOOD_JSON)
        errors = audit_consistency(output, WIKI_ONLY_CONTEXT)
        assert any(
            e.error_type == AuditErrorType.CONSISTENCY and "source_type" in e.field_path
            for e in errors
        )

    def test_passes_valid_output(self):
        _, output = audit_schema(GOOD_JSON)
        errors = audit_consistency(output, MOCK_CONTEXT)
        assert errors == []


class TestAuditOrchestrator:
    def test_full_audit_passes(self):
        result = audit(GOOD_JSON, MOCK_CONTEXT)
        assert result.passed is True
        assert result.errors == []

    def test_schema_failure_short_circuits(self):
        result = audit(BAD_SCHEMA_JSON, MOCK_CONTEXT)
        assert result.passed is False
        assert all(e.error_type == AuditErrorType.SCHEMA for e in result.errors)

    def test_grounding_failure(self):
        result = audit(BAD_GROUNDING_JSON, MOCK_CONTEXT)
        assert result.passed is False
        assert any(e.error_type == AuditErrorType.GROUNDING for e in result.errors)

    def test_audit_collects_grounding_and_consistency_errors(self):
        result = audit(BAD_GROUNDING_AND_DUPLICATE_JSON, MOCK_CONTEXT)
        assert result.passed is False
        error_types = {e.error_type for e in result.errors}
        assert AuditErrorType.GROUNDING in error_types
        assert AuditErrorType.CONSISTENCY in error_types
