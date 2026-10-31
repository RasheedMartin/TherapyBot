"""Keep the vector index in step with clinical documents: re-index exactly the document that changed."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from therapybot.models import ClinicalDocument


@receiver(post_save, sender=ClinicalDocument)
def reindex_document(sender, instance, raw=False, **kwargs):
    if raw:  # loading fixtures
        return
    from therapybot.rag.indexing import safely_index_document

    safely_index_document(instance)
