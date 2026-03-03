from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sherpa.context import RetrievedContext
from sherpa.producer import build_system_prompt, produce
from sherpa.schema import AuditError, AuditErrorType, RetrievedSource

MOCK_CONTEXT = RetrievedContext(
    sources={
        "wikipedia": [
            RetrievedSource(
                source_type="wikipedia",
                title="Test Page",
                url="https://en.wikipedia.org/wiki/Test_Page",
                text="Test content here.",
            )
        ],
        "arxiv": [],
    },
    display_names={
        "wikipedia": "Wikipedia",
        "arxiv": "arXiv",
    },
)


WIKI_ONLY_CONTEXT = RetrievedContext(
    sources={
        "wikipedia": [
            RetrievedSource(
                source_type="wikipedia",
                title="Test Page",
                url="https://en.wikipedia.org/wiki/Test_Page",
                text="Test content here.",
            )
        ],
        "arxiv": [],
    },
    display_names={
        "wikipedia": "Wikipedia",
        "arxiv": "arXiv",
    },
)


class TestBuildSystemPrompt:
    def test_includes_source_types(self):
        prompt = build_system_prompt(["wikipedia", "arxiv"])
        assert '"wikipedia"' in prompt
        assert '"arxiv"' in prompt

    def test_single_source_type(self):
        prompt = build_system_prompt(["wikipedia"])
        assert '"wikipedia"' in prompt

    def test_empty_source_types(self):
        prompt = build_system_prompt([])
        assert '"unknown"' in prompt

    def test_three_source_types(self):
        prompt = build_system_prompt(["wikipedia", "arxiv", "hackernews"])
        assert '"hackernews"' in prompt


class TestProduce:
    @pytest.mark.asyncio
    async def test_first_attempt_prompt_structure(self):
        captured_kwargs = {}
        mock_llm = AsyncMock()

        async def capture_chat(**kwargs):
            captured_kwargs.update(kwargs)
            return '{"mock": "response"}'

        mock_llm.chat = capture_chat

        await produce("quantum computing", MOCK_CONTEXT, mock_llm, attempt=1)

        messages = captured_kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert '"wikipedia"' in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "Query: quantum computing" in messages[1]["content"]
        assert "Test content here." in messages[1]["content"]
        assert "PREVIOUS ATTEMPT FAILED" not in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_retry_includes_error_block(self):
        captured_kwargs = {}
        mock_llm = AsyncMock()

        async def capture_chat(**kwargs):
            captured_kwargs.update(kwargs)
            return '{"mock": "response"}'

        mock_llm.chat = capture_chat

        errors = [
            AuditError(
                AuditErrorType.GROUNDING,
                "findings[0].supporting_sources[0].retrieved_snippet",
                "Snippet not found in context (match ratio: 42.0%, threshold: 75%)",
            ),
        ]

        await produce(
            "quantum computing",
            MOCK_CONTEXT,
            mock_llm,
            previous_errors=errors,
            attempt=2,
        )

        user_content = captured_kwargs["messages"][1]["content"]
        assert "PREVIOUS ATTEMPT FAILED" in user_content
        assert "[grounding]" in user_content
        assert "findings[0].supporting_sources[0].retrieved_snippet" in user_content
        assert "match ratio: 42.0%" in user_content

    @pytest.mark.asyncio
    async def test_multiple_errors_all_included(self):
        captured_kwargs = {}
        mock_llm = AsyncMock()

        async def capture_chat(**kwargs):
            captured_kwargs.update(kwargs)
            return '{"mock": "response"}'

        mock_llm.chat = capture_chat

        errors = [
            AuditError(AuditErrorType.SCHEMA, "findings", "field required"),
            AuditError(
                AuditErrorType.GROUNDING,
                "findings[0].supporting_sources[0].retrieved_snippet",
                "Snippet not found",
            ),
            AuditError(
                AuditErrorType.CONSISTENCY, "findings[1].claim", "Duplicate finding"
            ),
        ]

        await produce(
            "test query", MOCK_CONTEXT, mock_llm, previous_errors=errors, attempt=3
        )

        user_content = captured_kwargs["messages"][1]["content"]
        assert "[schema]" in user_content
        assert "[grounding]" in user_content
        assert "[consistency]" in user_content
        assert "field required" in user_content
        assert "Duplicate finding" in user_content

    @pytest.mark.asyncio
    async def test_json_response_format_requested(self):
        captured_kwargs = {}
        mock_llm = AsyncMock()

        async def capture_chat(**kwargs):
            captured_kwargs.update(kwargs)
            return '{"mock": "response"}'

        mock_llm.chat = capture_chat

        await produce("test", MOCK_CONTEXT, mock_llm)

        assert captured_kwargs["response_format"] == {"type": "json_object"}
        assert captured_kwargs["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_context_text_included_in_prompt(self):
        captured_kwargs = {}
        mock_llm = AsyncMock()

        async def capture_chat(**kwargs):
            captured_kwargs.update(kwargs)
            return '{"mock": "response"}'

        mock_llm.chat = capture_chat

        await produce("test", MOCK_CONTEXT, mock_llm)

        user_content = captured_kwargs["messages"][1]["content"]
        assert "=== Wikipedia ===" in user_content
        assert "Test Page" in user_content
        assert "Do NOT fabricate arXiv citations" in user_content

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='{"query": "test", "result": "data"}')

        result = await produce("test", MOCK_CONTEXT, mock_llm)

        assert result == '{"query": "test", "result": "data"}'

    @pytest.mark.asyncio
    async def test_prompt_only_includes_available_sources(self):
        captured_kwargs = {}
        mock_llm = AsyncMock()

        async def capture_chat(**kwargs):
            captured_kwargs.update(kwargs)
            return '{"mock": "response"}'

        mock_llm.chat = capture_chat

        await produce("test", WIKI_ONLY_CONTEXT, mock_llm)

        system_content = captured_kwargs["messages"][0]["content"]
        assert '"wikipedia"' in system_content
        assert '"arxiv"' not in system_content
