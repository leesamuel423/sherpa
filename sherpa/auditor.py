from __future__ import annotations

import json

from pydantic import ValidationError
from rapidfuzz import fuzz

from sherpa.config import settings
from sherpa.context import RetrievedContext
from sherpa.schema import AuditError, AuditErrorType, AuditResult, ResearchOutput


def audit_schema(raw_json: str) -> tuple[list[AuditError], ResearchOutput | None]:
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return [AuditError(AuditErrorType.SCHEMA, "$", f"Invalid JSON: {e}")], None

    try:
        output = ResearchOutput.model_validate(parsed)
        return [], output
    except ValidationError as e:
        errors = [
            AuditError(
                AuditErrorType.SCHEMA,
                ".".join(str(p) for p in err["loc"]),
                err["msg"],
            )
            for err in e.errors()
        ]
        return errors, None


def audit_grounding(
    output: ResearchOutput, context: RetrievedContext
) -> list[AuditError]:
    errors = []
    full_context = context.as_text().lower()

    for i, finding in enumerate(output.findings):
        for j, source in enumerate(finding.supporting_sources):
            snippet = source.retrieved_snippet.lower()
            ratio = fuzz.partial_ratio(snippet, full_context)
            if ratio < settings.grounding_threshold:
                errors.append(
                    AuditError(
                        AuditErrorType.GROUNDING,
                        f"findings[{i}].supporting_sources[{j}].retrieved_snippet",
                        f"Snippet not found in context (match ratio: {ratio:.1f}%, threshold: {settings.grounding_threshold}%)",
                    )
                )
    return errors


def audit_consistency(
    output: ResearchOutput, context: RetrievedContext
) -> list[AuditError]:
    errors = []
    available = context.available_source_types

    seen_claims = set()
    for i, finding in enumerate(output.findings):
        normalized = finding.claim.strip().lower()
        if normalized in seen_claims:
            errors.append(
                AuditError(
                    AuditErrorType.CONSISTENCY,
                    f"findings[{i}].claim",
                    "Duplicate finding",
                )
            )
        seen_claims.add(normalized)

        for j, source in enumerate(finding.supporting_sources):
            if source.source_type not in available:
                errors.append(
                    AuditError(
                        AuditErrorType.CONSISTENCY,
                        f"findings[{i}].supporting_sources[{j}].source_type",
                        f"Source type '{source.source_type}' was not available in retrieved context",
                    )
                )

    return errors


def audit(raw_json: str, context: RetrievedContext) -> AuditResult:
    schema_errors, output = audit_schema(raw_json)
    if schema_errors:
        return AuditResult(passed=False, errors=schema_errors)

    assert output is not None

    errors = audit_grounding(output, context) + audit_consistency(output, context)
    if errors:
        return AuditResult(passed=False, errors=errors)

    return AuditResult(passed=True)
