from __future__ import annotations

import asyncio
import sys
import time

import structlog

from sherpa.auditor import audit
from sherpa.config import settings
from sherpa.context import RetrievedContext, extract_keywords, gather_context
from sherpa.llm_client import LLMClient, create_llm_client
from sherpa.producer import produce
from sherpa.schema import AuditMetadata, AuditResult, ResearchOutput

log = structlog.get_logger()


def _finalize(
    raw_json: str,
    attempt: int,
    elapsed: float,
    audit_result: AuditResult,
) -> ResearchOutput:
    output = ResearchOutput.model_validate_json(raw_json)
    output.audit = AuditMetadata(
        passed=True,
        attempts=attempt,
        errors=[],
        wall_clock_seconds=round(elapsed, 2),
    )
    return output


def _finalize_degraded(
    raw_json: str | None,
    attempts: int,
    elapsed: float,
    errors: list,
) -> ResearchOutput:
    error_strs = [f"[{e.error_type.value}] {e.field_path}: {e.message}" for e in errors]
    audit = AuditMetadata(
        passed=False,
        attempts=attempts,
        errors=error_strs,
        wall_clock_seconds=round(elapsed, 2),
    )

    if raw_json:
        try:
            output = ResearchOutput.model_validate_json(raw_json)
            output.audit = audit
            return output
        except Exception:
            pass

    return ResearchOutput.model_construct(
        query="",
        summary="Research could not be completed successfully.",
        findings=[],
        sources_consulted=[],
        audit=audit,
    )


async def run_agent_loop(
    query: str,
    context: RetrievedContext,
    llm_client: LLMClient,
) -> ResearchOutput:
    start = time.monotonic()
    last_output: str | None = None
    last_errors = []

    for attempt in range(1, settings.max_attempts + 1):
        elapsed = time.monotonic() - start
        if elapsed >= settings.wall_clock_limit_seconds:
            log.warning("wall_clock_exceeded", attempt=attempt, elapsed=elapsed)
            break

        raw_json = await produce(
            query,
            context,
            llm_client,
            previous_errors=last_errors or None,
            attempt=attempt,
        )
        audit_result = audit(raw_json, context)

        log.info(
            "audit_complete",
            attempt=attempt,
            passed=audit_result.passed,
            error_types=[e.error_type.value for e in audit_result.errors],
            duration_ms=round((time.monotonic() - start) * 1000),
        )

        if audit_result.passed:
            return _finalize(raw_json, attempt, time.monotonic() - start, audit_result)

        last_output = raw_json
        last_errors = audit_result.errors
        log.info(
            "audit_failed", attempt=attempt, errors=[e.message for e in last_errors]
        )

    elapsed = time.monotonic() - start
    return _finalize_degraded(last_output, settings.max_attempts, elapsed, last_errors)


async def run(query: str) -> ResearchOutput:
    llm_client = create_llm_client()

    log.info("extracting_keywords", query=query)
    keywords = await extract_keywords(query, llm_client)
    log.info("keywords_extracted", keywords=keywords)

    log.info("gathering_context", keywords=keywords)
    context = await gather_context(keywords)
    available = {name: bool(items) for name, items in context.sources.items()}
    log.info("context_gathered", **available)

    result = await run_agent_loop(query, context, llm_client)
    log.info(
        "loop_complete",
        passed=result.audit.passed,
        total_attempts=result.audit.attempts,
        wall_clock_s=result.audit.wall_clock_seconds,
    )
    return result


def _configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if sys.stderr.isatty()
                else structlog.processors.JSONRenderer()
            ),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def main():
    _configure_logging()

    if len(sys.argv) < 2:
        print("Usage: python main.py <research query>", file=sys.stderr)
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    result = asyncio.run(run(query))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
