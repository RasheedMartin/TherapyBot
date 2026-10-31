"""
General reference knowledge (skill guides + MedlinePlus articles) and retrieval over it. Chunks live in
Postgres (pgvector), so every server process sees an update as soon as it's synced.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from therapybot.rag.chunking import parse_front_matter

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(settings.BASE_DIR) / "knowledge"
# Showing a link is a stronger claim than informing a reply, so it needs a clearer match
MIN_SOURCE_RELEVANCE = float(settings.RAG_MIN_SOURCE_RELEVANCE)
# Chunks scoring below this cosine similarity are treated as off-topic and not shown to the model
MIN_RELEVANCE = float(settings.RAG_MIN_RELEVANCE)


@dataclass
class Document:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def load_knowledge_documents() -> list[Document]:
    """Skill guides from KNOWLEDGE_DIR plus active reference articles from the database."""
    from therapybot.models import KnowledgeArticle

    documents = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        # The H1 just repeats the title (kept in metadata); alone it would become an empty chunk
        body = re.sub(r"\A# .*\n+", "", body)
        # Guard against indexing error pages or other junk
        if len(body) < 200 or "<html" in body.lower() or "403 forbidden" in body.lower():
            raise ValueError(f"{path.name} doesn't look like a knowledge article; refusing to index it")
        meta.setdefault("title", path.stem.replace("-", " "))
        meta["file_name"] = path.name
        documents.append(Document(id=path.name, text=body, metadata=meta))

    for article in KnowledgeArticle.objects.filter(active=True):
        documents.append(
            Document(
                id=f"article-{article.pk}",
                text=article.body,
                metadata={"title": article.title, "url": article.url, "source": article.source},
            )
        )
    if not documents:
        raise ValueError(f"No knowledge articles found in {KNOWLEDGE_DIR} or the database")
    return documents


def build_index(if_stale: bool = False) -> bool:
    """
    Sync the reference corpus into the vector store. Only changed content is re-embedded; returns False
    when nothing changed. (`if_stale` is accepted for the boot command's sake; syncing is always incremental.)
    """
    from therapybot.rag.indexing import sync_reference_corpus

    return sync_reference_corpus(load_knowledge_documents())


def retrieve_context(query: str, top_k: int = 3, sources: list | None = None) -> str:
    """
    Best-effort retrieval of on-topic reference material; returns "" if none applies.
    Articles with a public URL that were used are appended to `sources` for "related reading".
    """
    if len(query.split()) < 4:
        return ""  # greetings and one-word replies embed too vaguely to retrieve anything useful
    try:
        from therapybot.rag.retrieval import search_reference

        results = search_reference(query, top_k)
    except Exception:
        logger.error("Context retrieval failed; answering without it", exc_info=True)
        return ""

    from therapybot.articles import passes_topic_gate

    sections = []
    for chunk, score in results:
        text, meta = chunk.text.strip(), chunk.metadata or {}
        # Topic-specific articles (e.g. suicide, eating disorders) are only used when the user raised the topic
        if not text or score < MIN_RELEVANCE or not passes_topic_gate(meta.get("url"), query):
            continue
        sections.append(f"[{meta.get('title', 'Reference')}]\n{text}")
        # Offer at most one article to read, and only a strong match
        if sources is not None and not sources and meta.get("url") and score >= MIN_SOURCE_RELEVANCE:
            sources.append({"title": meta["title"], "url": meta["url"], "source": meta.get("source", "")})
    if not sections:
        return ""
    joined = "\n\n---\n\n".join(sections)
    return (
        "Background notes you may draw on if they genuinely fit what the user needs right now. "
        "Pick at most one or two ideas, put them in your own words, and never mention these notes.\n\n"
        f"{joined}"
    )
