# research-agent

Self-healing evidence-backed research agent.

## Overview

Queries Wikipedia, arXiv, and Hacker News in parallel, synthesizes findings via LLM (Groq default, with OpenAI and Anthropic also supported), and outputs structured JSON. Every claim is grounded with a verbatim snippet verified through fuzzy string matching (rapidfuzz). A **Producer → Auditor → Repairer** loop auto-retries up to 3 attempts or 60 seconds wall clock, whichever comes first. On failure, the agent returns degraded output with full audit metadata — it never crashes silently.

## Quick start

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
cp .env.example .env   # add your LLM API key (Groq is the easiest to start)
make install
make run QUERY="quantum computing"
```

Output is structured JSON printed to stdout. Logs go to stderr.

Exit codes: `0` on success (always — check `audit.passed` for validation status), `1` if no query argument is provided.

## Configuration

All settings live in `.env` and are loaded via `pydantic-settings` with type validation. Missing required keys fail fast at startup.

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `groq` | LLM provider: `groq`, `openai`, or `anthropic` |
| `GROQ_API_KEY` | *(empty)* | Required when `LLM_PROVIDER=groq` |
| `OPENAI_API_KEY` | *(empty)* | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | *(empty)* | Required when `LLM_PROVIDER=anthropic` |
| `LLM_MODEL` | *(auto per provider)* | Override model. Defaults: `llama-3.3-70b-versatile` (Groq), `gpt-4o-mini` (OpenAI), `claude-sonnet-4-20250514` (Anthropic) |
| `MAX_ATTEMPTS` | `3` | Max audit-repair cycles |
| `WALL_CLOCK_LIMIT_SECONDS` | `60.0` | Hard timeout for the entire loop |
| `GROUNDING_THRESHOLD` | `75.0` | rapidfuzz `partial_ratio` cutoff (%) |
| `ENABLE_LLM_CONSISTENCY_CHECK` | `false` | LLM-based contradiction check (adds latency) |
| `KEYWORD_STRATEGY` | `llm` | `llm` or `regex` |
| `LOG_LEVEL` | `INFO` | structlog level |
| `ENABLED_SOURCES` | `["wikipedia","arxiv"]` | Active sources. Available: `wikipedia`, `arxiv`, `hackernews` |
| `SOURCE_WIKIPEDIA_MAX_SENTENCES` | `10` | Wikipedia extract length |
| `SOURCE_ARXIV_MAX_RESULTS` | `3` | Max arXiv papers fetched |
| `SOURCE_HACKERNEWS_MAX_STORIES` | `5` | Max Hacker News stories fetched |
| `API_TIMEOUT_SECONDS` | `5.0` | Per-API-call timeout |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  User Query → Keyword Extraction → Parallel Retrieval       │
│              (Wikipedia + arXiv + HN via httpx)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   CONTEXT ASSEMBLY     │
              │ Availability tags per  │
              │ source (found / empty) │
              └───────────┬────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │         AGENT LOOP            │
          │  max 3 attempts OR 60s wall   │
          │                               │
          │  ┌──────────┐                 │
          │  │ PRODUCER │── raw JSON      │
          │  └──────────┘       │         │
          │                     ▼         │
          │  ┌──────────────────────────┐ │
          │  │ AUDITOR                  │ │
          │  │  1. Schema  (Pydantic)   │ │
          │  │  2. Grounding (rapidfuzz)│ │
          │  │  3. Consistency (determ.)│ │
          │  └──────────┬───────────────┘ │
          │             │                 │
          │     pass? ──┤── no ──┐        │
          │     │                ▼        │
          │     ▼          ┌──────────┐   │
          │   OUTPUT       │ REPAIRER │   │
          │                │(=Producer│   │
          │                │+errors)  │   │
          │                └──────────┘   │
          └───────────────────────────────┘
```

### Components

- **`context.py`** — Keyword extraction (LLM or regex strategy) and context assembly with availability markers. Delegates source fetching to the `sources/` subpackage.
- **`sources/`** — Pluggable source registry. Each source implements the `SourceFetcher` protocol (`fetch(keywords) → list[RetrievedSource]`). Includes `wikipedia.py` (MediaWiki Action API), `arxiv.py` (Atom API), and `hackernews.py` (Algolia HN Search API). `get_enabled_fetchers()` loads sources from the `ENABLED_SOURCES` config.
- **`producer.py`** — Constructs the synthesis prompt with a few-shot example and schema definition. On retries, injects the Auditor's typed error list so the LLM can target fixes. The Repairer is the same function with `previous_errors` set.
- **`auditor.py`** — Three-stage pipeline with typed errors. Schema errors short-circuit (grounding/consistency need a parsed object), but grounding and consistency run together to surface all errors in one pass:
  1. **Schema** — `json.loads()` + Pydantic `model_validate`. Catches malformed JSON and missing/invalid fields.
  2. **Grounding** — `rapidfuzz.fuzz.partial_ratio` checks that every `retrieved_snippet` appears in the fetched context (threshold: 75%).
  3. **Consistency** — No duplicate claims, no citations of unavailable sources, valid source types.
- **`llm_client.py`** — Protocol-based async LLM interface with three implementations: `GroqClient`, `OpenAIClient`, `AnthropicClient`. Selected at runtime by `LLM_PROVIDER` config. Swap providers by changing one env var.
- **`main.py`** — CLI entry point, structlog configuration, and the retry loop orchestrator. Returns `ResearchOutput` JSON to stdout.
- **`schema.py`** — Pydantic models (`ResearchOutput`, `Finding`, `Source`, `AuditMetadata`) and internal audit types (`AuditError`, `AuditResult`).
- **`config.py`** — `pydantic-settings` with `.env` loading and type validation.

## Repository structure

```
sherpa/
├── main.py           # CLI entry point and retry loop
├── producer.py       # LLM prompt construction
├── auditor.py        # Three-stage validation pipeline
├── context.py        # Keyword extraction and context assembly
├── schema.py         # Pydantic models
├── config.py         # pydantic-settings configuration
├── llm_client.py     # Multi-provider LLM abstraction
└── sources/
    ├── __init__.py   # SourceFetcher protocol and registry
    ├── wikipedia.py
    ├── arxiv.py
    └── hackernews.py
tests/
├── conftest.py       # Mock LLM clients
├── fixtures.py       # Canned JSON responses
├── test_auditor.py
├── test_context.py
├── test_e2e.py
├── test_loop.py
├── test_producer.py
└── test_sources/
    ├── test_arxiv.py
    ├── test_hackernews.py
    └── test_wikipedia.py
```

## Output schema

The agent always returns a `ResearchOutput` JSON object:

```
ResearchOutput
├── query: str                    # Original research query
├── summary: str                  # 1-3 sentence summary (max 1000 chars)
├── findings: [Finding]           # At least one
│   ├── claim: str                # Single factual assertion
│   ├── supporting_sources: [Source]  # At least one per finding
│   │   ├── source_type: "wikipedia" | "arxiv" | "hackernews"
│   │   ├── title: str
│   │   ├── url: str
│   │   └── retrieved_snippet: str    # Verbatim excerpt from context
│   └── confidence: float         # 0.0–1.0
├── sources_consulted: [Source]   # All sources used
└── audit: AuditMetadata
    ├── passed: bool              # Did it pass all checks?
    ├── attempts: int             # How many tries it took
    ├── errors: [str]             # Empty if passed, error list if degraded
    └── wall_clock_seconds: float # Total loop time
```

**Example (trimmed):**

```json
{
  "query": "quantum computing",
  "summary": "Quantum computing leverages quantum mechanical phenomena...",
  "findings": [
    {
      "claim": "Quantum computers use qubits instead of classical bits.",
      "supporting_sources": [
        {
          "source_type": "wikipedia",
          "title": "Quantum computing",
          "url": "https://en.wikipedia.org/wiki/Quantum_computing",
          "retrieved_snippet": "A quantum computer is a computer that exploits quantum mechanical phenomena."
        }
      ],
      "confidence": 0.92
    }
  ],
  "sources_consulted": [ "..." ],
  "audit": {
    "passed": true,
    "attempts": 1,
    "errors": [],
    "wall_clock_seconds": 4.21
  }
}
```

Callers must check `audit.passed` before trusting the output. On failure (`passed: false`), `audit.errors` contains the final Auditor error list.

`source_type` is a plain string (not an enum) for extensibility — new sources can be added without modifying the schema.

## Development

```bash
make help       # list all targets
make install    # uv sync
make test       # 77 tests, async tests auto-detected via asyncio_mode = "auto"
make fmt        # format with black
make fmt-check  # check formatting without modifying
make run QUERY="your query here"
make clean      # remove __pycache__ / .pytest_cache
```

Logs render as human-readable colored output in interactive terminals. When stderr is piped or redirected, output switches to JSON (one object per line) for machine parsing. Pipe to `jq` for analysis:

```bash
make run QUERY="quantum computing" 2>logs.jsonl
cat logs.jsonl | jq 'select(.event == "audit_complete")'
```

## Design decisions

These are some of the architectural tradeoffs shaping the agent's design.

### Groq + Llama 3.3 over OpenAI

The default provider is Groq (Llama 3.3 70B) rather than OpenAI's `gpt-4o-mini`, trading some structured output reliability for significantly lower cost and higher throughput. The three-stage Auditor pipeline compensates — schema failures caught by Pydantic validation trigger automatic retries, so the system self-heals even when the LLM's JSON compliance is imperfect. The LLM interface is provider-agnostic (a single `Protocol` type), so swapping back to OpenAI or another provider requires implementing one class.

### Deterministic grounding over LLM judge

Using an LLM to verify that claims are grounded in retrieved context is circular — you're auditing an LLM with another LLM. Measured accuracy on textual entailment benchmarks for models in this tier is 70–80%, meaning 1 in 4 checks could be wrong.

Instead, the Producer emits `retrieved_snippet` (a verbatim excerpt) and the Auditor verifies grounding deterministically via `rapidfuzz.fuzz.partial_ratio`. This is faster (no API call), cheaper (zero tokens), deterministic (same input always produces same result), and debuggable (you can log the exact ratio and threshold).

**Why 75% threshold?** Encoding differences (Unicode normalization, whitespace collapsing, HTML entity artifacts) between raw API responses and LLM reproduction cause legitimate snippets to score 80–95% rather than 100%. 75% accommodates these artifacts while catching fabricated quotes (which typically score below 50%).

### Full re-emission over partial JSON patches

The original design proposed the Repairer emit JSON Patch (RFC 6902). This is a trap: producing valid JSON Patch operations is itself a hard structured-output problem — you're solving structured output failures with another structured output task. Instead, the Producer re-emits the complete JSON with corrections on retry. The token cost of re-emitting ~500 tokens is trivial.

### Repairer collapsed into Producer

A separate Repairer agent with its own system prompt adds complexity without adding capability. The repair task is identical to production — "produce valid JSON given this context" — with the additional constraint of "fix these specific errors." A single `produce()` function with an optional `previous_errors` parameter handles both cases, reducing codebase size and eliminating prompt drift between two templates.

### Schema-first development

Three key decisions in the schema:

- **`retrieved_snippet` is mandatory on every source.** This converts grounding from an unreliable LLM entailment judgment into a deterministic fuzzy string match.
- **`confidence` is a float, not categorical.** Downstream consumers get a filterable threshold rather than subjective "high/medium/low."
- **`AuditMetadata` is always present.** Even on success. Callers never guess whether output was validated.

### Direct MediaWiki API over `wikipedia` package

The `wikipedia` Python package is unmaintained and introduces hard-to-handle failure modes (`DisambiguationError`, `PageError`, no response size control). Hitting the MediaWiki Action API directly via `httpx` provides `exsentences` to cap response length, `exintro` for introduction-only extracts, standard HTTP error codes, and one fewer dependency.

### `structlog` for observability

A multi-step retry loop is difficult to debug with print statements. When Attempt 2 fails and Attempt 3 succeeds, you need structured records showing exactly what the Auditor flagged. `structlog` with JSON output gives correlation by attempt number, filterable fields, and machine-parseable logs pipeable to `jq`.

### `pydantic-settings` over shell env vars

Hardcoding API keys in a shell script is a leak vector. `pydantic-settings` reads from `.env` with type validation, so a missing `GROQ_API_KEY` fails fast with a clear error instead of silently passing an empty string to the API client.

### Dynamic source registry

Sources are loaded at runtime via a `SourceFetcher` protocol and an `ENABLED_SOURCES` config list. Adding a new source means implementing `fetch(keywords) → list[RetrievedSource]` and registering it in the registry — no changes to `context.py`, `producer.py`, or the audit pipeline. This also lets operators disable sources that are slow or irrelevant for their domain without code changes.

### Multi-provider LLM support

LLM providers (`groq`, `openai`, `anthropic`) are optional dependencies declared in `pyproject.toml`. Each provider is imported lazily in its client class, so the agent only requires the SDK for the active provider. Swapping providers means changing `LLM_PROVIDER` in `.env` — the `create_llm_client()` factory handles the rest. Default models are auto-selected per provider but can be overridden with `LLM_MODEL`.

### Wall-clock timeout

Capping at 3 attempts without a time bound means that if the LLM provider is slow (cold starts, rate limiting), three attempts at 30 seconds each means 90+ seconds of dead air. The 60-second wall clock breaks the loop regardless, ensuring bounded response time.

## Dependencies

Five core runtime dependencies:

| Package | Why |
|---|---|
| `httpx` | Async HTTP for all data source APIs |
| `pydantic` | Schema validation for the output contract |
| `pydantic-settings` | Type-validated config from `.env` |
| `rapidfuzz` | Fuzzy string matching for grounding verification |
| `structlog` | Structured JSON logging for observability |

Optional LLM provider (install one):

| Package | When |
|---|---|
| `groq` | `LLM_PROVIDER=groq` (default) |
| `openai` | `LLM_PROVIDER=openai` |
| `anthropic` | `LLM_PROVIDER=anthropic` |

Install with extras: `uv sync --extra groq` or `uv sync --extra all` for all providers.

Dev: `pytest`, `pytest-asyncio`, `groq` (default-provider test fixtures), `black` (formatter).
