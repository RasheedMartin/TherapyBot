"""Provider-neutral interfaces for chat models and embeddings."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


def system(content: str) -> ChatMessage:
    return ChatMessage("system", content)


def user(content: str) -> ChatMessage:
    return ChatMessage("user", content)


def assistant(content: str) -> ChatMessage:
    return ChatMessage("assistant", content)


class ChatModel(Protocol):
    """A chat completion model. Implementations must return only the answer, never hidden reasoning."""

    def complete(self, messages: list[ChatMessage]) -> str: ...

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]: ...


class Embedder(Protocol):
    """Turns text into vectors. Queries and documents may be embedded differently (e.g. bge query prefix)."""

    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...
