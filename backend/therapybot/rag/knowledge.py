"""
General reference knowledge (skill guides + MedlinePlus articles) and retrieval over it.

The index is persisted to storage/ as JSON + a NumPy matrix and reloaded when another process
rebuilds it. (Phase 2 of the therapist refactor moves this into Postgres with pgvector.)
"""

import hashlib
import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from django.conf import settings

from therapybot import llm
from therapybot.rag.chunking import embedding_text, parse_front_matter, split_markdown

logger = logging.getLogger(__name__)

INDEX_DIR = Path(settings.BASE_DIR) / "storage"
INDEX_FILE = INDEX_DIR / "index.json"
VECTORS_FILE = INDEX_DIR / "embeddings.npy"
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


@dataclass
class Chunk:
    text: str
    metadata: dict


class VectorIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray):
        self.chunks = chunks
        self.vectors = vectors  # rows are L2-normalized, so a dot product is cosine similarity

    def search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        q = np.asarray(llm.get_embedder().embed_query(query), dtype=np.float32)
        q /= np.linalg.norm(q) or 1.0
        scores = self.vectors @ q
        best = np.argsort(-scores)[:top_k]
        return [(self.chunks[i], float(scores[i])) for i in best]


_index: VectorIndex | None = None
_index_mtime: float | None = None
_index_lock = threading.Lock()


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


def _content_hash(documents: list[Document]) -> str:
    digest = hashlib.sha256(settings.EMBED_MODEL_NAME.encode())
    for doc in sorted(documents, key=lambda d: d.id):
        digest.update(doc.id.encode())
        digest.update(doc.text.encode())
        digest.update(json.dumps(doc.metadata, sort_keys=True).encode())
    return digest.hexdigest()


def build_index(if_stale: bool = False) -> VectorIndex | None:
    """Embed all knowledge documents and persist the index. With if_stale, skip when nothing changed."""
    global _index, _index_mtime
    documents = load_knowledge_documents()
    content_hash = _content_hash(documents)
    if if_stale and INDEX_FILE.exists() and json.loads(INDEX_FILE.read_text()).get("hash") == content_hash:
        logger.info("Knowledge index is up to date")
        return None

    chunks = [
        Chunk(text=section, metadata={**doc.metadata, "header_path": header_path})
        for doc in documents
        for section, header_path in split_markdown(doc.text)
    ]
    logger.info("Building index from %d knowledge documents (%d chunks)", len(documents), len(chunks))
    # Metadata (title, source URL, heading path) gives each section its topic; a bare "## Getting started"
    # section is ambiguous on its own. Relevance cutoffs in settings are calibrated for this format.
    embedded = llm.get_embedder().embed_documents([embedding_text(c.text, c.metadata) for c in chunks])
    vectors = np.asarray(embedded, dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)

    INDEX_DIR.mkdir(exist_ok=True)
    np.save(VECTORS_FILE, vectors)
    # Written last: its mtime tells other processes a complete new index is ready
    INDEX_FILE.write_text(json.dumps({
        "hash": content_hash,
        "model": settings.EMBED_MODEL_NAME,
        "documents": len(documents),
        "chunks": [{"text": c.text, "metadata": c.metadata} for c in chunks],
    }))
    _index, _index_mtime = VectorIndex(chunks, vectors), INDEX_FILE.stat().st_mtime
    logger.info("Index saved to %s", INDEX_DIR)
    return _index


def get_index() -> VectorIndex | None:
    """Load the persisted index, reloading when another process has rebuilt it. Returns None if unavailable."""
    global _index, _index_mtime
    mtime = INDEX_FILE.stat().st_mtime if INDEX_FILE.exists() else None
    if _index is not None and mtime == _index_mtime:
        return _index
    with _index_lock:
        if (_index is None or mtime != _index_mtime) and mtime is not None and VECTORS_FILE.exists():
            data = json.loads(INDEX_FILE.read_text())
            chunks = [Chunk(text=c["text"], metadata=c["metadata"]) for c in data["chunks"]]
            _index, _index_mtime = VectorIndex(chunks, np.load(VECTORS_FILE)), mtime
            logger.info("Loaded vector index from %s", INDEX_DIR)
    return _index


def retrieve_context(query: str, top_k: int = 3, sources: list | None = None) -> str:
    """
    Best-effort retrieval of on-topic reference material; returns "" if none applies.
    Articles with a public URL that were used are appended to `sources` for "related reading".
    """
    if len(query.split()) < 4:
        return ""  # greetings and one-word replies embed too vaguely to retrieve anything useful
    try:
        index = get_index()
        if index is None:
            return ""
        results = index.search(query, top_k)
    except Exception:
        logger.error("Context retrieval failed; answering without it", exc_info=True)
        return ""

    from therapybot.articles import passes_topic_gate

    sections = []
    for chunk, score in results:
        text, meta = chunk.text.strip(), chunk.metadata
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
