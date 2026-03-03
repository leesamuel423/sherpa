# Sherpa — Research Agent

## Overview

Sherpa is a research agent that queries public data sources, synthesizes findings, and outputs structured JSON. It runs a **Producer → Auditor → Repairer** pipeline: the Producer (LLM) generates a `ResearchOutput`, the Auditor validates it (schema → grounding → consistency), and on failure the Producer is re-called with typed errors injected into the prompt. The loop is capped at **3 attempts or 60 seconds** wall clock. The Repairer is not a separate agent — it's the Producer with error context.

## File Map

| File | Purpose |
|---|---|
| `sherpa/main.py` | CLI entry point, agent loop orchestration |
| `sherpa/producer.py` | Prompt construction and LLM call (+ repair path) |
| `sherpa/auditor.py` | Three-stage audit: schema (Pydantic), grounding (rapidfuzz), consistency |
| `sherpa/context.py` | Parallel retrieval, context assembly with availability tags |
| `sherpa/schema.py` | All Pydantic models (`ResearchOutput`, `Finding`, `Source`, `AuditError`, etc.) |
| `sherpa/config.py` | `pydantic-settings` config loaded from `.env` |
| `sherpa/llm_client.py` | Provider-agnostic async LLM interface (OpenAI, Groq, Anthropic) |
| `sherpa/sources/__init__.py` | `SourceFetcher` protocol + registry of available sources |
| `sherpa/sources/wikipedia.py` | MediaWiki Action API fetcher |
| `sherpa/sources/arxiv.py` | arXiv Atom API fetcher |
| `sherpa/sources/hackernews.py` | Hacker News API fetcher |
| `tests/` | Unit tests (auditor, schema) and integration tests (mock LLM loop) |

## Key Conventions

- **Grounding invariant**: Every `retrieved_snippet` must be a near-verbatim quote from fetched context. The auditor uses `rapidfuzz.partial_ratio` with a **75% threshold** (`GROUNDING_THRESHOLD` in config). Below that → `GROUNDING` error → retry.
- **Degraded output is valid**: When the loop exhausts attempts or wall clock, it returns `ResearchOutput` with `audit.passed = False` and the error list. Callers must check `audit.passed` before trusting the output.
- **Partial source failure**: If a source API fails or returns nothing, context assembly marks it `[Unavailable]`. The Producer prompt forbids citing unavailable sources.

## Extending

### Adding a source

1. Create `sherpa/sources/myapi.py` with a class implementing `SourceFetcher` (needs `name`, `display_name` attrs and an `async fetch(keywords) -> list[RetrievedSource]` method)
2. Import and register it in `sherpa/sources/__init__.py` `_build_registry()`
3. Add to `ENABLED_SOURCES` in `.env` (comma-separated list)
4. Add any source-specific config fields to `Settings` in `config.py`

### Swapping LLM provider

Set `LLM_PROVIDER` in `.env` to `openai`, `groq`, or `anthropic` and supply the corresponding API key. Model selection is via `LLM_MODEL`.

## Dev Commands

```
make install    # uv sync
make test       # uv run pytest -v
make run QUERY="quantum computing"
make fmt        # black sherpa tests
make fmt-check  # black --check
make clean      # remove __pycache__ / .pytest_cache
```
