from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field

import structlog

from sherpa.config import settings
from sherpa.schema import RetrievedSource

log = structlog.get_logger()


@dataclass
class RetrievedContext:
    sources: dict[str, list[RetrievedSource]] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)

    @property
    def available_source_types(self) -> list[str]:
        return [name for name, items in self.sources.items() if items]

    def as_text(self) -> str:
        parts = []
        for name, display in self.display_names.items():
            items = self.sources.get(name, [])
            if items:
                parts.append(f"=== {display} ===")
                for src in items:
                    parts.append(f"Title: {src.title}\nURL: {src.url}\n{src.text}\n")
            else:
                parts.append(
                    f"[{display}: No results found for this query. Do NOT fabricate {display} citations.]"
                )
        return "\n\n".join(parts)


async def gather_context(keywords: list[str], fetchers=None) -> RetrievedContext:
    if fetchers is None:
        from sherpa.sources import get_enabled_fetchers

        fetchers = get_enabled_fetchers(settings.enabled_sources)

    tasks = [f.fetch(keywords) for f in fetchers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    sources: dict[str, list[RetrievedSource]] = {}
    display_names: dict[str, str] = {}

    for fetcher, result in zip(fetchers, results):
        display_names[fetcher.name] = fetcher.display_name
        if isinstance(result, (Exception, BaseException)):
            log.warning("source_fetch_failed", source=fetcher.name, error=str(result))
            sources[fetcher.name] = []
        else:
            sources[fetcher.name] = result

    return RetrievedContext(sources=sources, display_names=display_names)


STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "about",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        "i",
        "me",
        "my",
        "myself",
        "we",
        "our",
        "you",
        "your",
        "he",
        "him",
        "his",
        "she",
        "her",
        "it",
        "its",
        "they",
        "them",
        "their",
        "and",
        "but",
        "or",
        "if",
        "because",
        "while",
        "although",
        "tell",
        "explain",
        "describe",
        "find",
        "search",
        "look",
        "give",
        "show",
    }
)


def _extract_keywords_regex(query: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", query.lower())
    keywords = [w for w in words if w not in STOPWORDS and len(w) > 2]
    return keywords[:4] if keywords else query.lower().split()[:4]


async def _extract_keywords_llm(query: str, llm_client) -> list[str]:
    messages = [
        {
            "role": "system",
            "content": (
                "Extract 2-4 search keywords from this research query. "
                'Return only a JSON array of strings. Example: ["quantum", "computing", "qubits"]'
            ),
        },
        {"role": "user", "content": query},
    ]
    raw = await llm_client.chat(
        messages=messages,
        response_format={"type": "json_object"},
        max_tokens=100,
    )
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed[:4]
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v[:4]
    except (json.JSONDecodeError, TypeError):
        pass
    log.warning("keyword_extraction_llm_fallback", raw=raw)
    return _extract_keywords_regex(query)


async def extract_keywords(query: str, llm_client=None) -> list[str]:
    strategy = settings.keyword_strategy
    if strategy == "llm" and llm_client is not None:
        return await _extract_keywords_llm(query, llm_client)
    return _extract_keywords_regex(query)
