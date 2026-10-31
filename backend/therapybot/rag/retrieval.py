"""
The only way to read chunks. `search_client_record` is the choke point for clinical data: it requires an
actor and a client, authorizes (and audits) the access, filters to that one client in SQL, and re-checks
every result before returning it.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

from django.db.models import Q
from pgvector.django import CosineDistance

from therapybot import llm
from therapybot.models import Chunk, ClinicalDocument
from therapybot.permissions import authorize_client

MAX_CLIENT_CHUNKS = 5000  # far above any real record; a guard against runaway queries
RRF_K = 60  # reciprocal rank fusion constant
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-']*")


class IsolationError(RuntimeError):
    """A retrieved chunk didn't belong to the requested client. Should be impossible; fail loudly."""


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    text: str
    score: float
    document_id: int | None
    session_id: int | None
    session_date: str | None
    doc_type: str


def _client_scope(client) -> Q:
    """A client's record: the practice's documents for them, plus their own uploads once linked."""
    scope = Q(client_id=client.pk)
    if client.user_id:
        scope |= Q(owner_id=client.user_id, doc_type=ClinicalDocument.DocType.CLIENT_UPLOAD)
    return scope


def _belongs(chunk: Chunk, client) -> bool:
    if chunk.corpus != Chunk.Corpus.CLIENT_RECORD:
        return False
    return chunk.client_id == client.pk or (
        client.user_id is not None
        and chunk.owner_id == client.user_id
        and chunk.doc_type == ClinicalDocument.DocType.CLIENT_UPLOAD
    )


def _keyword_scores(query: str, chunks: list[Chunk]) -> dict[int, float]:
    """BM25 over this client's chunks, for exact terms (names, medications, dates) vectors can miss."""
    terms = set(_WORD_RE.findall(query.lower()))
    if not terms or not chunks:
        return {}
    docs = {c.pk: Counter(_WORD_RE.findall(c.text.lower())) for c in chunks}
    avg_len = sum(sum(d.values()) for d in docs.values()) / len(docs) or 1.0
    scores = {}
    for pk, counts in docs.items():
        length, score = sum(counts.values()), 0.0
        for term in terms:
            tf = counts.get(term, 0)
            if not tf:
                continue
            df = sum(1 for d in docs.values() if term in d)
            idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / avg_len))
        if score:
            scores[pk] = score
    return scores


def search_client_record(*, actor, client_id, query: str, k: int = 6, request=None,
                         purpose: str = "record.search") -> list[RetrievedChunk]:
    """
    Search one client's record on behalf of `actor`. Raises Http404 unless the actor may access this
    client (see permissions.authorize_client). Results fuse vector and keyword ranking.
    """
    client = authorize_client(actor, client_id, purpose, request=request)
    query_vector = llm.get_embedder().embed_query(query)
    chunks = list(
        Chunk.objects.filter(corpus=Chunk.Corpus.CLIENT_RECORD)
        .filter(_client_scope(client))
        .annotate(distance=CosineDistance("embedding", query_vector))
        .order_by("distance")[:MAX_CLIENT_CHUNKS]
    )
    for chunk in chunks:  # defense in depth: the SQL filter above is the real guard
        if not _belongs(chunk, client):
            raise IsolationError(f"Chunk {chunk.pk} is outside client {client.pk}'s record")

    vector_rank = {c.pk: rank for rank, c in enumerate(chunks)}
    keyword = _keyword_scores(query, chunks)
    keyword_rank = {pk: rank for rank, pk in enumerate(sorted(keyword, key=keyword.get, reverse=True))}
    fused = {
        c.pk: 1 / (RRF_K + vector_rank[c.pk]) + (1 / (RRF_K + keyword_rank[c.pk]) if c.pk in keyword_rank else 0)
        for c in chunks
    }
    by_id = {c.pk: c for c in chunks}
    best = sorted(fused, key=fused.get, reverse=True)[:k]
    return [
        RetrievedChunk(
            chunk_id=pk,
            text=by_id[pk].text,
            score=fused[pk],
            document_id=by_id[pk].document_id,
            session_id=by_id[pk].session_id,
            session_date=by_id[pk].session_date.isoformat() if by_id[pk].session_date else None,
            doc_type=by_id[pk].doc_type,
        )
        for pk in best
    ]


def search_reference(query: str, k: int = 3) -> list[tuple[Chunk, float]]:
    """General reference material (skill guides, articles). Never touches client records."""
    query_vector = llm.get_embedder().embed_query(query)
    chunks = (
        Chunk.objects.filter(corpus=Chunk.Corpus.CLINICAL_REFERENCE)
        .annotate(distance=CosineDistance("embedding", query_vector))
        .order_by("distance")[:k]
    )
    return [(chunk, 1.0 - chunk.distance) for chunk in chunks]
