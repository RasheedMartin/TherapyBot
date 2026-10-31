"""
Turn documents into embedded chunks. Clinical documents are re-indexed one at a time when they change;
the reference corpus is re-synced only when its content changes.
"""

import hashlib
import logging
import re

from django.db import transaction

from therapybot import llm
from therapybot.models import Chunk, ClinicalDocument
from therapybot.rag.chunking import embedding_text, split_markdown

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 1200


def split_clinical_text(text: str) -> list[str]:
    """Markdown sections if the text has headings; otherwise paragraphs packed into ~1200-character chunks."""
    if re.search(r"^#+\s", text, re.M):
        return [section for section, _ in split_markdown(text)]
    chunks, current = [], ""
    for paragraph in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if not paragraph:
            continue
        if current and len(current) + len(paragraph) + 2 > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = ""
        # A single paragraph longer than the limit is split on sentence boundaries
        while len(paragraph) > MAX_CHUNK_CHARS:
            cut = paragraph.rfind(". ", 0, MAX_CHUNK_CHARS) + 1 or MAX_CHUNK_CHARS
            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def index_document(doc: ClinicalDocument) -> int:
    """
    Replace this document's chunks (and only this document's). Embeds before deleting the old chunks,
    so a failure leaves the previous index in place. Returns the number of chunks written.
    """
    sections = split_clinical_text(doc.text or "")
    # Metadata is embedded for topic context but deliberately excludes the title (it may identify someone)
    meta = {"type": doc.get_doc_type_display()}
    if doc.session_date:
        meta["date"] = doc.session_date.isoformat()
    texts = [embedding_text(section, meta) for section in sections]
    vectors = llm.get_embedder().embed_documents(texts) if texts else []

    with transaction.atomic():
        Chunk.objects.filter(document=doc).delete()
        Chunk.objects.bulk_create([
            Chunk(
                corpus=Chunk.Corpus.CLIENT_RECORD,
                practice_id=doc.client.practice_id if doc.client_id else None,
                client_id=doc.client_id,
                owner_id=doc.owner_id,
                document=doc,
                source_key=f"doc:{doc.pk}",
                session_id=doc.session_id,
                session_date=doc.session_date,
                doc_type=doc.doc_type,
                chunk_index=i,
                text=section,
                embedding=vector,
                content_hash=_hash(text),
            )
            for i, (section, text, vector) in enumerate(zip(sections, texts, vectors))
        ])
    return len(sections)


def safely_index_document(doc: ClinicalDocument) -> None:
    """Index on save without ever blocking the save; failures are logged and fixable with `reindex`."""
    try:
        index_document(doc)
    except Exception:
        logger.exception("Indexing failed for document %s; run `manage.py reindex` to repair", doc.pk)


def sync_reference_corpus(documents) -> bool:
    """
    Make the clinical_reference chunks match `documents` (skill guides and articles). Returns False when
    they already matched, so boot-time syncs are cheap.
    """
    planned = []
    for doc in documents:
        for i, (section, header_path) in enumerate(split_markdown(doc.text)):
            metadata = {**doc.metadata, "header_path": header_path}
            text = embedding_text(section, metadata)
            planned.append((doc, i, section, metadata, text))

    wanted = {(doc.id, i, _hash(text)) for doc, i, _, _, text in planned}
    existing = set(
        Chunk.objects.filter(corpus=Chunk.Corpus.CLINICAL_REFERENCE).values_list("source_key", "chunk_index", "content_hash")
    )
    if wanted == existing:
        return False

    vectors = llm.get_embedder().embed_documents([text for *_, text in planned])
    with transaction.atomic():
        Chunk.objects.filter(corpus=Chunk.Corpus.CLINICAL_REFERENCE).delete()
        Chunk.objects.bulk_create([
            Chunk(
                corpus=Chunk.Corpus.CLINICAL_REFERENCE,
                article_id=int(doc.id.split("-", 1)[1]) if doc.id.startswith("article-") else None,
                source_key=doc.id,
                chunk_index=i,
                text=section,
                metadata=metadata,
                embedding=vector,
                content_hash=_hash(text),
            )
            for (doc, i, section, metadata, text), vector in zip(planned, vectors)
        ])
    logger.info("Reference corpus synced: %d chunks from %d documents", len(planned), len(documents))
    return True
