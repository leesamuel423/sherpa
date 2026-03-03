from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from sherpa.context import (
    RetrievedContext,
    _extract_keywords_regex,
    _extract_keywords_llm,
    extract_keywords,
    gather_context,
)
from sherpa.schema import RetrievedSource

MOCK_WIKI_SOURCES = [
    RetrievedSource(
        "wikipedia",
        "Quantum computing",
        "https://en.wikipedia.org/wiki/Quantum_computing",
        "QC text.",
    ),
]
MOCK_ARXIV_SOURCES = [
    RetrievedSource(
        "arxiv", "QEC Paper", "http://arxiv.org/abs/2401.00001", "QEC text."
    ),
]


class _FakeFetcher:
    def __init__(self, name: str, display_name: str, result=None, error=None):
        self.name = name
        self.display_name = display_name
        self._result = result
        self._error = error

    async def fetch(self, keywords: list[str]) -> list[RetrievedSource]:
        if self._error:
            raise self._error
        return self._result or []


class TestGatherContext:
    @pytest.mark.asyncio
    async def test_both_sources_succeed(self):
        fetchers = [
            _FakeFetcher("wikipedia", "Wikipedia", result=MOCK_WIKI_SOURCES),
            _FakeFetcher("arxiv", "arXiv", result=MOCK_ARXIV_SOURCES),
        ]
        ctx = await gather_context(["quantum"], fetchers=fetchers)

        assert len(ctx.sources["wikipedia"]) == 1
        assert len(ctx.sources["arxiv"]) == 1
        assert "wikipedia" in ctx.available_source_types
        assert "arxiv" in ctx.available_source_types

    @pytest.mark.asyncio
    async def test_wikipedia_fails_arxiv_succeeds(self):
        fetchers = [
            _FakeFetcher("wikipedia", "Wikipedia", error=Exception("wiki timeout")),
            _FakeFetcher("arxiv", "arXiv", result=MOCK_ARXIV_SOURCES),
        ]
        ctx = await gather_context(["quantum"], fetchers=fetchers)

        assert ctx.sources["wikipedia"] == []
        assert len(ctx.sources["arxiv"]) == 1
        assert "wikipedia" not in ctx.available_source_types
        assert "arxiv" in ctx.available_source_types

    @pytest.mark.asyncio
    async def test_arxiv_fails_wikipedia_succeeds(self):
        fetchers = [
            _FakeFetcher("wikipedia", "Wikipedia", result=MOCK_WIKI_SOURCES),
            _FakeFetcher("arxiv", "arXiv", error=Exception("503")),
        ]
        ctx = await gather_context(["quantum"], fetchers=fetchers)

        assert len(ctx.sources["wikipedia"]) == 1
        assert ctx.sources["arxiv"] == []

    @pytest.mark.asyncio
    async def test_both_fail_returns_empty(self):
        fetchers = [
            _FakeFetcher("wikipedia", "Wikipedia", error=Exception("timeout")),
            _FakeFetcher("arxiv", "arXiv", error=Exception("timeout")),
        ]
        ctx = await gather_context(["quantum"], fetchers=fetchers)

        assert ctx.sources["wikipedia"] == []
        assert ctx.sources["arxiv"] == []
        assert ctx.available_source_types == []


class TestRetrievedContextAsText:
    def test_both_sources(self):
        ctx = RetrievedContext(
            sources={
                "wikipedia": [
                    RetrievedSource(
                        "wikipedia", "Page", "http://wiki/Page", "Wiki text."
                    )
                ],
                "arxiv": [
                    RetrievedSource("arxiv", "Paper", "http://arxiv/1", "Arxiv text.")
                ],
            },
            display_names={"wikipedia": "Wikipedia", "arxiv": "arXiv"},
        )
        text = ctx.as_text()
        assert "=== Wikipedia ===" in text
        assert "Wiki text." in text
        assert "=== arXiv ===" in text
        assert "Arxiv text." in text

    def test_wikipedia_only(self):
        ctx = RetrievedContext(
            sources={
                "wikipedia": [
                    RetrievedSource(
                        "wikipedia", "Page", "http://wiki/Page", "Wiki text."
                    )
                ],
                "arxiv": [],
            },
            display_names={"wikipedia": "Wikipedia", "arxiv": "arXiv"},
        )
        text = ctx.as_text()
        assert "=== Wikipedia ===" in text
        assert "Do NOT fabricate arXiv citations" in text

    def test_no_sources(self):
        ctx = RetrievedContext(
            sources={"wikipedia": [], "arxiv": []},
            display_names={"wikipedia": "Wikipedia", "arxiv": "arXiv"},
        )
        text = ctx.as_text()
        assert "Do NOT fabricate Wikipedia citations" in text
        assert "Do NOT fabricate arXiv citations" in text


class TestExtractKeywordsRegex:
    def test_filters_stopwords(self):
        keywords = _extract_keywords_regex("what is quantum computing")
        assert "what" not in keywords
        assert "quantum" in keywords
        assert "computing" in keywords

    def test_limits_to_four(self):
        keywords = _extract_keywords_regex(
            "machine learning artificial intelligence neural networks deep learning"
        )
        assert len(keywords) <= 4

    def test_short_words_filtered(self):
        keywords = _extract_keywords_regex("I am an AI")
        assert len(keywords) > 0

    def test_empty_after_filtering_uses_fallback(self):
        keywords = _extract_keywords_regex("is the")
        assert len(keywords) > 0

    def test_numbers_preserved(self):
        keywords = _extract_keywords_regex("GPT4 architecture vs H100 performance")
        token_text = " ".join(keywords)
        assert "gpt4" in token_text or "h100" in token_text


class TestExtractKeywordsLLM:
    @pytest.mark.asyncio
    async def test_parses_json_array(self):
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='["quantum", "computing"]')
        keywords = await _extract_keywords_llm("quantum computing", mock_llm)
        assert keywords == ["quantum", "computing"]

    @pytest.mark.asyncio
    async def test_parses_json_object_with_array_value(self):
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='{"keywords": ["quantum", "computing"]}')
        keywords = await _extract_keywords_llm("quantum computing", mock_llm)
        assert keywords == ["quantum", "computing"]

    @pytest.mark.asyncio
    async def test_limits_to_four(self):
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='["a", "b", "c", "d", "e"]')
        keywords = await _extract_keywords_llm("long query", mock_llm)
        assert len(keywords) == 4

    @pytest.mark.asyncio
    async def test_falls_back_on_invalid_json(self):
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="not json at all")
        keywords = await _extract_keywords_llm("quantum computing", mock_llm)
        assert "quantum" in keywords


class TestExtractKeywords:
    @pytest.mark.asyncio
    async def test_llm_strategy_with_client(self):
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='["deep", "learning"]')
        with patch("sherpa.context.settings") as mock_settings:
            mock_settings.keyword_strategy = "llm"
            keywords = await extract_keywords("deep learning", mock_llm)
        assert keywords == ["deep", "learning"]

    @pytest.mark.asyncio
    async def test_regex_strategy(self):
        with patch("sherpa.context.settings") as mock_settings:
            mock_settings.keyword_strategy = "regex"
            keywords = await extract_keywords("quantum computing basics")
        assert "quantum" in keywords
        assert "computing" in keywords

    @pytest.mark.asyncio
    async def test_llm_strategy_without_client_falls_back(self):
        with patch("sherpa.context.settings") as mock_settings:
            mock_settings.keyword_strategy = "llm"
            keywords = await extract_keywords("quantum computing", llm_client=None)
        assert "quantum" in keywords
