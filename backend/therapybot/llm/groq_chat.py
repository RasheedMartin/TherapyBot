"""Groq chat models via the official SDK. Groq has no BAA with us: synthetic data only (see PHI_ALLOWED)."""

import os
from collections.abc import Iterator

from therapybot.llm.base import ChatMessage


class GroqChatModel:
    def __init__(self, model: str, *, temperature: float, max_tokens: int, timeout: float, max_retries: int):
        from groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable not set")
        self.model = model
        self._client = Groq(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self._params = {"temperature": temperature, "max_completion_tokens": max_tokens}
        # gpt-oss models reason before answering; keep that brief. Reasoning comes back in a separate
        # field, so `content` is only ever the answer.
        if "gpt-oss" in model:
            self._params["reasoning_effort"] = "low"

    def _payload(self, messages: list[ChatMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        extra = {"response_format": {"type": "json_object"}} if json_mode else {}
        response = self._client.chat.completions.create(
            model=self.model, messages=self._payload(messages), **self._params, **extra
        )
        return (response.choices[0].message.content or "").strip()

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        chunks = self._client.chat.completions.create(
            model=self.model, messages=self._payload(messages), stream=True, **self._params
        )
        for chunk in chunks:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
