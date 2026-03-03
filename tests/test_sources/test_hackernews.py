from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from sherpa.sources.hackernews import HackerNewsFetcher

DUMMY_REQUEST = httpx.Request("GET", "https://example.com")


def _hn_response(hits: list | None = None, status: int = 200) -> httpx.Response:
    body = {"hits": hits or []}
    return httpx.Response(status, json=body, request=DUMMY_REQUEST)


SAMPLE_HN_HITS = [
    {
        "objectID": "12345",
        "title": "Show HN: Quantum Computing Simulator",
        "url": "https://example.com/quantum-sim",
        "story_text": "We built a quantum computing simulator that runs in the browser.",
        "comment_text": None,
    },
    {
        "objectID": "67890",
        "title": "Understanding Qubits",
        "url": "",
        "story_text": "",
        "comment_text": "Great explanation of how qubits work in practice.",
    },
]


def _mock_async_client(response: httpx.Response):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


def _mock_async_client_raising(exc: Exception):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=exc)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


class TestHackerNewsFetcher:
    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        resp = _hn_response(SAMPLE_HN_HITS)
        fetcher = HackerNewsFetcher()
        with patch(
            "sherpa.sources.hackernews.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["quantum", "computing"])

        assert len(sources) == 2
        assert sources[0].source_type == "hackernews"
        assert sources[0].title == "Show HN: Quantum Computing Simulator"
        assert sources[0].url == "https://example.com/quantum-sim"
        assert "quantum computing simulator" in sources[0].text.lower()

    @pytest.mark.asyncio
    async def test_empty_results(self):
        resp = _hn_response(hits=[])
        fetcher = HackerNewsFetcher()
        with patch(
            "sherpa.sources.hackernews.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["xyznonexistent"])

        assert sources == []

    @pytest.mark.asyncio
    async def test_fallback_url_uses_hn_item_link(self):
        hits = [
            {
                "objectID": "99999",
                "title": "No URL Story",
                "url": "",
                "story_text": "A story without an external URL.",
                "comment_text": None,
            },
        ]
        resp = _hn_response(hits)
        fetcher = HackerNewsFetcher()
        with patch(
            "sherpa.sources.hackernews.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["test"])

        assert len(sources) == 1
        assert "news.ycombinator.com/item?id=99999" in sources[0].url

    @pytest.mark.asyncio
    async def test_comment_text_used_when_no_story_text(self):
        resp = _hn_response(SAMPLE_HN_HITS)
        fetcher = HackerNewsFetcher()
        with patch(
            "sherpa.sources.hackernews.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["qubits"])

        assert "qubits work in practice" in sources[1].text.lower()

    @pytest.mark.asyncio
    async def test_http_error_raises(self):
        resp = httpx.Response(500, text="Server Error", request=DUMMY_REQUEST)
        fetcher = HackerNewsFetcher()
        with patch(
            "sherpa.sources.hackernews.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        fetcher = HackerNewsFetcher()
        with patch(
            "sherpa.sources.hackernews.httpx.AsyncClient",
            return_value=_mock_async_client_raising(httpx.TimeoutException("timeout")),
        ):
            with pytest.raises(httpx.TimeoutException):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_hit_with_no_text_skipped(self):
        hits = [
            {
                "objectID": "11111",
                "title": "",
                "url": "",
                "story_text": "",
                "comment_text": "",
            },
            {
                "objectID": "22222",
                "title": "Has Content",
                "url": "https://example.com",
                "story_text": "Real story content here.",
                "comment_text": None,
            },
        ]
        resp = _hn_response(hits)
        fetcher = HackerNewsFetcher()
        with patch(
            "sherpa.sources.hackernews.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["test"])

        assert len(sources) == 1
        assert sources[0].title == "Has Content"
