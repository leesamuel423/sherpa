from __future__ import annotations

import pytest

from sherpa.main import run_agent_loop
from tests.conftest import MockLLMClient
from tests.fixtures import BAD_GROUNDING_JSON, BAD_SCHEMA_JSON, GOOD_JSON, MOCK_CONTEXT


@pytest.mark.asyncio
async def test_first_attempt_success():
    client = MockLLMClient([GOOD_JSON])
    result = await run_agent_loop("quantum computing", MOCK_CONTEXT, client)
    assert result.audit.passed is True
    assert result.audit.attempts == 1


@pytest.mark.asyncio
async def test_recovery_from_grounding_failure():
    client = MockLLMClient([BAD_GROUNDING_JSON, GOOD_JSON])
    result = await run_agent_loop("quantum computing", MOCK_CONTEXT, client)
    assert result.audit.passed is True
    assert result.audit.attempts == 2


@pytest.mark.asyncio
async def test_recovery_from_schema_failure():
    client = MockLLMClient([BAD_SCHEMA_JSON, GOOD_JSON])
    result = await run_agent_loop("quantum computing", MOCK_CONTEXT, client)
    assert result.audit.passed is True
    assert result.audit.attempts == 2


@pytest.mark.asyncio
async def test_loop_exhaustion_returns_degraded():
    client = MockLLMClient([BAD_GROUNDING_JSON, BAD_GROUNDING_JSON, BAD_GROUNDING_JSON])
    result = await run_agent_loop("quantum computing", MOCK_CONTEXT, client)
    assert result.audit.passed is False
    assert result.audit.attempts == 3
    assert len(result.audit.errors) > 0


@pytest.mark.asyncio
async def test_degraded_output_has_typed_findings():
    """When JSON is valid but fails grounding, degraded output should have proper Finding objects."""
    client = MockLLMClient([BAD_GROUNDING_JSON, BAD_GROUNDING_JSON, BAD_GROUNDING_JSON])
    result = await run_agent_loop("quantum computing", MOCK_CONTEXT, client)
    assert result.audit.passed is False
    for finding in result.findings:
        assert hasattr(finding, "claim")
        assert hasattr(finding, "confidence")
        for src in finding.supporting_sources:
            assert hasattr(src, "source_type")
            assert hasattr(src, "retrieved_snippet")


@pytest.mark.asyncio
async def test_degraded_output_with_unparseable_json():
    """When JSON is completely broken, degraded output should have empty findings."""
    client = MockLLMClient(["not json {{{", "not json {{{", "not json {{{"])
    result = await run_agent_loop("quantum computing", MOCK_CONTEXT, client)
    assert result.audit.passed is False
    assert result.findings == []
    assert result.sources_consulted == []
