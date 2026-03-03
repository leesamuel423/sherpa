from __future__ import annotations

import httpx

from sherpa.config import settings
from sherpa.schema import RetrievedSource

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsFetcher:
    name: str = "hackernews"
    display_name: str = "Hacker News"

    async def fetch(self, keywords: list[str]) -> list[RetrievedSource]:
        query = " ".join(keywords)
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": settings.source_hackernews_max_stories,
        }
        timeout = httpx.Timeout(settings.api_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(HN_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        hits = data.get("hits", [])
        sources = []
        for hit in hits:
            title = hit.get("title", "")
            story_text = hit.get("story_text") or ""
            comment_text = hit.get("comment_text") or ""
            text = story_text or comment_text or title
            if not text:
                continue
            object_id = hit.get("objectID", "")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            sources.append(
                RetrievedSource(
                    source_type="hackernews",
                    title=title,
                    url=url,
                    text=text,
                )
            )
        return sources
