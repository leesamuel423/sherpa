from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from sherpa.sources.wikipedia import WikipediaFetcher

DUMMY_REQUEST = httpx.Request("GET", "https://example.com")


def _wiki_response(pages: dict | None = None, status: int = 200) -> httpx.Response:
    body = {"query": {"pages": pages}} if pages else {}
    return httpx.Response(status, json=body, request=DUMMY_REQUEST)


SAMPLE_WIKI_PAGES = {
    "12345": {
        "pageid": 12345,
        "title": "Quantum computing",
        "extract": "Quantum computing is a type of computation.",
    },
    "67890": {
        "pageid": 67890,
        "title": "Qubit",
        "extract": "A qubit is a two-state quantum-mechanical system.",
    },
}


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


class TestWikipediaFetcher:
    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        resp = _wiki_response(SAMPLE_WIKI_PAGES)
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["quantum", "computing"])

        assert len(sources) == 2
        titles = {s.title for s in sources}
        assert "Quantum computing" in titles
        assert "Qubit" in titles
        for s in sources:
            assert s.source_type == "wikipedia"
            assert s.url.startswith("https://en.wikipedia.org/wiki/")
            assert len(s.text) > 0

    @pytest.mark.asyncio
    async def test_empty_results(self):
        resp = _wiki_response(pages=None)
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["xyznonexistent"])

        assert sources == []

    @pytest.mark.asyncio
    async def test_pages_with_empty_extract(self):
        pages = {
            "111": {"pageid": 111, "title": "Empty Page", "extract": ""},
            "222": {
                "pageid": 222,
                "title": "Has Content",
                "extract": "Some content here.",
            },
        }
        resp = _wiki_response(pages)
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["test"])

        assert len(sources) == 1
        assert sources[0].title == "Has Content"

    @pytest.mark.asyncio
    async def test_http_error_raises(self):
        resp = httpx.Response(500, text="Internal Server Error", request=DUMMY_REQUEST)
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_http_429_raises(self):
        resp = httpx.Response(429, text="Too Many Requests", request=DUMMY_REQUEST)
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client_raising(httpx.TimeoutException("timeout")),
        ):
            with pytest.raises(httpx.TimeoutException):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_malformed_json_response(self):
        resp = httpx.Response(200, text="not json {{{", request=DUMMY_REQUEST)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=resp)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        fetcher = WikipediaFetcher()
        with patch("sherpa.sources.wikipedia.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(Exception):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_unexpected_json_structure(self):
        resp = httpx.Response(200, json={"unexpected": "shape"}, request=DUMMY_REQUEST)
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["test"])
        assert sources == []

    @pytest.mark.asyncio
    async def test_url_encodes_special_characters(self):
        pages = {
            "99": {
                "pageid": 99,
                "title": "Schrödinger's cat",
                "extract": "A thought experiment.",
            },
        }
        resp = _wiki_response(pages)
        fetcher = WikipediaFetcher()
        with patch(
            "sherpa.sources.wikipedia.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["schrodinger", "cat"])

        assert len(sources) == 1
        url = sources[0].url
        assert "'" not in url
        assert "ö" not in url
        assert "Schr%C3%B6dinger" in url
