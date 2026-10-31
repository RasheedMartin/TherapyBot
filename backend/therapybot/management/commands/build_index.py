from django.core.management.base import BaseCommand

from therapybot.rag import INDEX_DIR, build_index


class Command(BaseCommand):
    help = "Rebuild the retrieval index in storage/ from knowledge/*.md and active KnowledgeArticles."

    def add_arguments(self, parser):
        parser.add_argument("--if-stale", action="store_true", help="Only rebuild when the content has changed")

    def handle(self, *args, if_stale=False, **options):
        if build_index(if_stale=if_stale) is None:
            self.stdout.write("Index already up to date")
        else:
            self.stdout.write(self.style.SUCCESS(f"Index rebuilt at {INDEX_DIR}"))
