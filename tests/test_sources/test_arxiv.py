from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from sherpa.sources.arxiv import ArxivFetcher

DUMMY_REQUEST = httpx.Request("GET", "https://example.com")

SAMPLE_ARXIV_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001</id>
    <title>Quantum Error Correction</title>
    <summary>We review quantum error correction codes for fault-tolerant computation.</summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002</id>
    <title>Topological Qubits</title>
    <summary>Topological approaches to building stable qubits are explored.</summary>
  </entry>
</feed>
"""


def _arxiv_response(xml: str = SAMPLE_ARXIV_XML, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=xml, request=DUMMY_REQUEST)


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


class TestArxivFetcher:
    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        resp = _arxiv_response()
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["quantum"])

        assert len(sources) == 2
        assert sources[0].title == "Quantum Error Correction"
        assert sources[0].source_type == "arxiv"
        assert sources[0].url == "http://arxiv.org/abs/2401.00001"
        assert "error correction" in sources[0].text.lower()
        assert sources[1].title == "Topological Qubits"

    @pytest.mark.asyncio
    async def test_empty_feed(self):
        xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        resp = _arxiv_response(xml)
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["xyznonexistent"])

        assert sources == []

    @pytest.mark.asyncio
    async def test_entry_missing_fields_skipped(self):
        xml = """\
<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00003</id>
    <title>Has Title Only</title>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00004</id>
    <title>Complete Entry</title>
    <summary>This entry has all fields.</summary>
  </entry>
</feed>
"""
        resp = _arxiv_response(xml)
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["test"])

        assert len(sources) == 1
        assert sources[0].title == "Complete Entry"

    @pytest.mark.asyncio
    async def test_whitespace_normalization(self):
        xml = """\
<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00005</id>
    <title>
      Multi Line
      Title   Here
    </title>
    <summary>
      Summary with   lots   of
      whitespace   everywhere.
    </summary>
  </entry>
</feed>
"""
        resp = _arxiv_response(xml)
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["test"])

        assert sources[0].title == "Multi Line Title Here"
        assert sources[0].text == "Summary with lots of whitespace everywhere."

    @pytest.mark.asyncio
    async def test_http_error_raises(self):
        resp = httpx.Response(503, text="Service Unavailable", request=DUMMY_REQUEST)
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_http_429_raises(self):
        resp = httpx.Response(429, text="Too Many Requests", request=DUMMY_REQUEST)
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client_raising(httpx.TimeoutException("timeout")),
        ):
            with pytest.raises(httpx.TimeoutException):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_malformed_xml(self):
        resp = _arxiv_response(xml="<not valid xml at all", status=200)
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            with pytest.raises(Exception):
                await fetcher.fetch(["test"])

    @pytest.mark.asyncio
    async def test_xml_with_no_entries(self):
        xml = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</totalResults></feed>'
        resp = _arxiv_response(xml)
        fetcher = ArxivFetcher()
        with patch(
            "sherpa.sources.arxiv.httpx.AsyncClient",
            return_value=_mock_async_client(resp),
        ):
            sources = await fetcher.fetch(["nonexistent"])
        assert sources == []
