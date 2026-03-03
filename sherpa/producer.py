from __future__ import annotations

import structlog

from sherpa.context import RetrievedContext
from sherpa.llm_client import LLMClient
from sherpa.schema import AuditError

log = structlog.get_logger()

_PROMPT_TEMPLATE = """\
You are a research synthesizer. Given the context below, produce a JSON object matching the provided schema EXACTLY.

CRITICAL RULES:
- Every claim in `findings` MUST include a `retrieved_snippet` that is a VERBATIM quote copied directly from the context below. Do not paraphrase.
- Only cite sources that appear in the context. If a source is marked [Unavailable] or [No results found], do not reference it.
- If prior attempt errors are provided, fix ONLY those specific issues.
- The `audit` field should have: passed=true, attempts=1, errors=[], wall_clock_seconds=0.0 (these will be overwritten by the system).
- `confidence` should be between 0.0 and 1.0, reflecting how well the context supports the claim.
- `summary` must be under 1000 characters.
- Each finding needs at least one supporting source with a verbatim snippet.

OUTPUT SCHEMA:
{{
  "query": "<the user's research query>",
  "summary": "<1-3 sentence summary, max 1000 chars>",
  "findings": [
    {{
      "claim": "<single factual assertion>",
      "supporting_sources": [
        {{
          "source_type": {source_type_hint},
          "title": "<title of the source>",
          "url": "<url of the source>",
          "retrieved_snippet": "<VERBATIM quote from context>"
        }}
      ],
      "confidence": 0.0-1.0
    }}
  ],
  "sources_consulted": [
    {{
      "source_type": {source_type_hint},
      "title": "<title>",
      "url": "<url>",
      "retrieved_snippet": "<verbatim excerpt from context>"
    }}
  ],
  "audit": {{"passed": true, "attempts": 1, "errors": [], "wall_clock_seconds": 0.0}}
}}

EXAMPLE OUTPUT:
{{
  "query": "machine learning basics",
  "summary": "Machine learning is a subset of AI focused on algorithms that learn from data.",
  "findings": [
    {{
      "claim": "Machine learning algorithms improve through experience.",
      "supporting_sources": [
        {{
          "source_type": "wikipedia",
          "title": "Machine learning",
          "url": "https://en.wikipedia.org/wiki/Machine_learning",
          "retrieved_snippet": "Machine learning algorithms build a model based on sample data in order to make predictions or decisions without being explicitly programmed to do so."
        }}
      ],
      "confidence": 0.92
    }}
  ],
  "sources_consulted": [
    {{
      "source_type": "wikipedia",
      "title": "Machine learning",
      "url": "https://en.wikipedia.org/wiki/Machine_learning",
      "retrieved_snippet": "Machine learning algorithms build a model based on sample data"
    }}
  ],
  "audit": {{"passed": true, "attempts": 1, "errors": [], "wall_clock_seconds": 0.0}}
}}
"""


def build_system_prompt(source_types: list[str]) -> str:
    if source_types:
        hint = " | ".join(f'"{st}"' for st in source_types)
    else:
        hint = '"unknown"'
    return _PROMPT_TEMPLATE.format(source_type_hint=hint)


async def produce(
    query: str,
    context: RetrievedContext,
    llm_client: LLMClient,
    previous_errors: list[AuditError] | None = None,
    attempt: int = 1,
) -> str:
    error_block = ""
    if previous_errors:
        error_block = "PREVIOUS ATTEMPT FAILED. Fix these specific errors:\n"
        for err in previous_errors:
            error_block += (
                f"  - [{err.error_type.value}] {err.field_path}: {err.message}\n"
            )
        error_block += "\nGenerate a COMPLETE corrected JSON output.\n\n"

    user_content = f"{error_block}Query: {query}\n\nContext:\n{context.as_text()}"

    system_prompt = build_system_prompt(context.available_source_types)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    log.info(
        "producer_called",
        attempt=attempt,
        has_previous_errors=bool(previous_errors),
        error_count=len(previous_errors) if previous_errors else 0,
    )

    return await llm_client.chat(
        messages=messages,
        response_format={"type": "json_object"},
        max_tokens=2000,
    )
