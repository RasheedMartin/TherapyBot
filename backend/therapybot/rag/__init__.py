"""Retrieval: reference knowledge for everyone, and per-client clinical records behind access checks."""

from therapybot.rag.knowledge import KNOWLEDGE_DIR, build_index, load_knowledge_documents, retrieve_context
from therapybot.rag.retrieval import (
    IsolationError,
    RetrievedChunk,
    recent_client_chunks,
    search_client_record,
    search_reference,
)

__all__ = [
    "KNOWLEDGE_DIR",
    "IsolationError",
    "RetrievedChunk",
    "build_index",
    "load_knowledge_documents",
    "recent_client_chunks",
    "retrieve_context",
    "search_client_record",
    "search_reference",
]
