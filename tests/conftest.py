from __future__ import annotations


class MockLLMClient:
    """Simple mock LLM that returns pre-canned responses in sequence."""

    def __init__(self, responses: list[str]):
        self._responses = iter(responses)

    async def chat(self, **kwargs) -> str:
        return next(self._responses)


class MockLLMClientWithKeywords:
    """Mock LLM where the first chat call returns keywords, subsequent calls return produce responses."""

    def __init__(self, keyword_response: str, produce_responses: list[str]):
        self._keyword_response = keyword_response
        self._produce_iter = iter(produce_responses)
        self._call_count = 0

    async def chat(self, **kwargs) -> str:
        self._call_count += 1
        if self._call_count == 1:
            return self._keyword_response
        return next(self._produce_iter)
