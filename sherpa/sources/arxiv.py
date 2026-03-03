from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from sherpa.config import settings
from sherpa.schema import RetrievedSource

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivFetcher:
    name: str = "arxiv"
    display_name: str = "arXiv"

    async def fetch(self, keywords: list[str]) -> list[RetrievedSource]:
        query = " AND ".join(f"all:{kw}" for kw in keywords)
        params = {
            "search_query": query,
            "max_results": settings.source_arxiv_max_results,
            "sortBy": "relevance",
        }
        timeout = httpx.Timeout(settings.api_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get("https://export.arxiv.org/api/query", params=params)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        entries = root.findall("atom:entry", ARXIV_NS)

        sources = []
        for entry in entries:
            title_el = entry.find("atom:title", ARXIV_NS)
            summary_el = entry.find("atom:summary", ARXIV_NS)
            id_el = entry.find("atom:id", ARXIV_NS)
            if title_el is None or summary_el is None or id_el is None:
                continue
            title = " ".join(title_el.text.strip().split())
            summary = " ".join(summary_el.text.strip().split())
            sources.append(
                RetrievedSource(
                    source_type="arxiv",
                    title=title,
                    url=id_el.text.strip(),
                    text=summary,
                )
            )
        return sources
