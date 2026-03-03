from __future__ import annotations

from unittest.mock import AsyncMock, patch

import json
import pytest

from sherpa.context import RetrievedContext
from sherpa.main import run
from sherpa.schema import RetrievedSource

from tests.conftest import MockLLMClientWithKeywords
from tests.fixtures import GOOD_JSON

MOCK_WIKI_SOURCES = [
    RetrievedSource(
        source_type="wikipedia",
        title="Quantum computing",
        url="https://en.wikipedia.org/wiki/Quantum_computing",
        text=(
            "Quantum computing is a type of computation whose operations can harness "
            "the phenomena of quantum mechanics, such as superposition, interference, "
            "and entanglement."
        ),
    )
]

MOCK_ARXIV_SOURCES = [
    RetrievedSource(
        source_type="arxiv",
        title="Quantum Error Correction Review",
        url="http://arxiv.org/abs/2401.00001",
        text=(
            "We present a comprehensive review of quantum error correction codes "
            "and fault-tolerant quantum computation. Quantum error correction is "
            "essential for building reliable quantum computers, as quantum bits are "
            "inherently fragile and susceptible to decoherence."
        ),
    )
]

MOCK_CONTEXT = RetrievedContext(
    sources={
        "wikipedia": MOCK_WIKI_SOURCES,
        "arxiv": MOCK_ARXIV_SOURCES,
    },
    display_names={
        "wikipedia": "Wikipedia",
        "arxiv": "arXiv",
    },
)


@pytest.mark.asyncio
async def test_full_pipeline_success():
    mock_client = MockLLMClientWithKeywords(
        keyword_response='["quantum", "computing"]',
        produce_responses=[GOOD_JSON],
    )

    with (
        patch("sherpa.main.create_llm_client", return_value=mock_client),
        patch("sherpa.main.gather_context", AsyncMock(return_value=MOCK_CONTEXT)),
    ):
        result = await run("quantum computing")

    assert result.audit.passed is True
    assert result.audit.attempts == 1
    assert result.query == "quantum computing"
    assert len(result.findings) >= 1
    assert len(result.sources_consulted) >= 1


@pytest.mark.asyncio
async def test_full_pipeline_with_degraded_context():
    wiki_only_context = RetrievedContext(
        sources={
            "wikipedia": MOCK_WIKI_SOURCES,
            "arxiv": [],
        },
        display_names={
            "wikipedia": "Wikipedia",
            "arxiv": "arXiv",
        },
    )

    data = json.loads(GOOD_JSON)
    data["findings"] = [
        f
        for f in data["findings"]
        if all(s["source_type"] == "wikipedia" for s in f["supporting_sources"])
    ]
    data["sources_consulted"] = [
        s for s in data["sources_consulted"] if s["source_type"] == "wikipedia"
    ]
    wiki_only_json = json.dumps(data)

    mock_client = MockLLMClientWithKeywords(
        keyword_response='["quantum", "computing"]',
        produce_responses=[wiki_only_json],
    )

    with (
        patch("sherpa.main.create_llm_client", return_value=mock_client),
        patch("sherpa.main.gather_context", AsyncMock(return_value=wiki_only_context)),
    ):
        result = await run("quantum computing")

    assert result.query == "quantum computing"
    assert result.audit.passed is True
    assert result.audit.attempts == 1
    assert all(
        s.source_type == "wikipedia"
        for f in result.findings
        for s in f.supporting_sources
    )
