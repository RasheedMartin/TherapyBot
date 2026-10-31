"""Reference material for retrieval."""

from django.db import models


class KnowledgeArticle(models.Model):
    """Reference material for retrieval, from public-domain or licensed sources. Editable in the admin."""

    title = models.CharField(max_length=200)
    url = models.URLField(unique=True)
    source = models.CharField(max_length=80)  # e.g. "MedlinePlus"
    body = models.TextField()  # Markdown with ## section headings
    active = models.BooleanField(default=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} ({self.source})"
