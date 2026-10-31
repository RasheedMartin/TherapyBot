from django.core.management.base import BaseCommand

from therapybot.models import ClinicalDocument
from therapybot.rag import build_index
from therapybot.rag.indexing import index_document


class Command(BaseCommand):
    help = "Re-embed every clinical document and re-sync the reference corpus (e.g. after changing models)."

    def handle(self, *args, **options):
        total = 0
        for doc in ClinicalDocument.objects.all().iterator():
            total += index_document(doc)
        build_index()
        self.stdout.write(self.style.SUCCESS(f"Re-indexed {total} clinical chunks and synced the reference corpus"))
