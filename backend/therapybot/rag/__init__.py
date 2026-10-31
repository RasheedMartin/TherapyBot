"""Retrieval over reference knowledge (and, later, per-client clinical records)."""

from therapybot.rag.knowledge import (
    INDEX_DIR,
    KNOWLEDGE_DIR,
    build_index,
    get_index,
    load_knowledge_documents,
    retrieve_context,
)

__all__ = ["INDEX_DIR", "KNOWLEDGE_DIR", "build_index", "get_index", "load_knowledge_documents", "retrieve_context"]
