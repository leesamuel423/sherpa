from __future__ import annotations

from urllib.parse import quote

import httpx

from sherpa.config import settings
from sherpa.schema import RetrievedSource


class WikipediaFetcher:
    name: str = "wikipedia"
    display_name: str = "Wikipedia"

    async def fetch(self, keywords: list[str]) -> list[RetrievedSource]:
        query = " ".join(keywords)
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exsentences": settings.source_wikipedia_max_sentences,
            "exlimit": 3,
            "explaintext": True,
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": 3,
        }
        timeout = httpx.Timeout(settings.api_timeout_seconds)
        headers = {
            "User-Agent": "ResearchAgent/0.1 (https://github.com/example; research-agent)"
        }
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            resp = await client.get("https://en.wikipedia.org/w/api.php", params=params)
            resp.raise_for_status()
            data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []

        sources = []
        for page_id, page in pages.items():
            title = page.get("title", "")
            extract = page.get("extract", "")
            if not extract:
                continue
            sources.append(
                RetrievedSource(
                    source_type="wikipedia",
                    title=title,
                    url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}",
                    text=extract,
                )
            )
        return sources
