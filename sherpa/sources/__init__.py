from __future__ import annotations

from typing import Protocol, runtime_checkable

from sherpa.schema import RetrievedSource


@runtime_checkable
class SourceFetcher(Protocol):
    name: str
    display_name: str

    async def fetch(self, keywords: list[str]) -> list[RetrievedSource]: ...


def _build_registry() -> dict[str, type[SourceFetcher]]:
    from sherpa.sources.arxiv import ArxivFetcher
    from sherpa.sources.hackernews import HackerNewsFetcher
    from sherpa.sources.wikipedia import WikipediaFetcher

    return {
        "wikipedia": WikipediaFetcher,
        "arxiv": ArxivFetcher,
        "hackernews": HackerNewsFetcher,
    }


def get_enabled_fetchers(names: list[str]) -> list[SourceFetcher]:
    registry = _build_registry()
    fetchers = []
    for name in names:
        cls = registry.get(name)
        if cls is None:
            raise ValueError(
                f"Unknown source: {name!r}. Available: {', '.join(registry)}"
            )
        fetchers.append(cls())
    return fetchers
