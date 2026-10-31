"""
Retrievable chunks for vector search (pgvector). Only therapybot.rag may query this table: client
record chunks must always be fetched through rag.retrieval, which enforces access and isolation.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from pgvector.django import HnswIndex, VectorField

from therapybot.fields import EncryptedTextField

EMBEDDING_DIMENSIONS = 384  # BAAI/bge-small-en-v1.5


class Chunk(models.Model):
    class Corpus(models.TextChoices):
        CLIENT_RECORD = "client_record"
        CLINICAL_REFERENCE = "clinical_reference"

    corpus = models.CharField(max_length=20, choices=Corpus.choices)
    # Whose record this is. Practice records set client; a client's own uploads set owner (the account).
    practice = models.ForeignKey("Practice", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    client = models.ForeignKey("Client", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    # What it came from: exactly one of a clinical document, a reference article, or a knowledge file
    document = models.ForeignKey(
        "ClinicalDocument", on_delete=models.CASCADE, null=True, blank=True, related_name="chunks"
    )
    article = models.ForeignKey(
        "KnowledgeArticle", on_delete=models.CASCADE, null=True, blank=True, related_name="chunks"
    )
    source_key = models.CharField(max_length=120)  # "doc:12", "article:3", "file:sleep.md"
    session = models.ForeignKey("Session", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    session_date = models.DateField(null=True, blank=True)
    doc_type = models.CharField(max_length=20, blank=True)
    chunk_index = models.PositiveIntegerField()
    text = EncryptedTextField()
    metadata = models.JSONField(default=dict, blank=True)  # reference: title, url, source, header_path
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["corpus", "client"], name="chunk_corpus_client"),
            models.Index(fields=["corpus", "owner"], name="chunk_corpus_owner"),
            models.Index(fields=["source_key"], name="chunk_source"),
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]
        constraints = [
            # A client-record chunk without an owner could never be authorized, or worse, leak
            models.CheckConstraint(
                condition=Q(corpus="clinical_reference") | Q(client__isnull=False) | Q(owner__isnull=False),
                name="client_record_chunk_has_owner",
            ),
        ]

    def __str__(self):
        return f"{self.corpus} {self.source_key}#{self.chunk_index}"
