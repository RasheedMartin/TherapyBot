"""
Access to chat models and embeddings, behind provider-neutral interfaces.

Swap providers (e.g. to one that will sign a BAA) by adding a class that implements
ChatModel / Embedder in this package and selecting it with LLM_PROVIDER.
"""

import threading
from pathlib import Path

from django.conf import settings

from therapybot.llm.base import ChatMessage, ChatModel, Embedder, assistant, system, user

__all__ = ["ChatMessage", "ChatModel", "Embedder", "assistant", "system", "user", "get_chat_model", "get_embedder"]

_models: dict[bool, ChatModel] = {}
_embedder: Embedder | None = None
_lock = threading.Lock()


def get_chat_model(fast: bool = False) -> ChatModel:
    """The main conversational model, or (fast=True) a smaller one for screening and summaries."""
    with _lock:
        if fast not in _models:
            if settings.LLM_PROVIDER != "groq":
                raise RuntimeError(f"Unknown LLM_PROVIDER {settings.LLM_PROVIDER!r}")
            from therapybot.llm.groq_chat import GroqChatModel

            if fast:
                # The risk screener runs on every message, so ride out brief rate limiting (the SDK waits
                # for the server's retry-after) rather than silently falling back to keyword-only screening
                _models[fast] = GroqChatModel(
                    settings.GROQ_FAST_MODEL, temperature=0, max_tokens=400, timeout=8, max_retries=2
                )
            else:
                _models[fast] = GroqChatModel(
                    settings.GROQ_MODEL, temperature=0.6, max_tokens=1500, timeout=30, max_retries=1
                )
        return _models[fast]


def get_embedder() -> Embedder:
    global _embedder
    with _lock:
        if _embedder is None:
            from therapybot.llm.fastembed_embedder import FastEmbedEmbedder

            cache = settings.FASTEMBED_CACHE_PATH or str(Path(settings.BASE_DIR) / ".fastembed_cache")
            _embedder = FastEmbedEmbedder(settings.EMBED_MODEL_NAME, cache_dir=cache)
        return _embedder
