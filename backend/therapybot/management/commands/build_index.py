from django.core.management.base import BaseCommand

from therapybot.rag import build_index


class Command(BaseCommand):
    help = "Sync the reference corpus (knowledge/*.md and active KnowledgeArticles) into the vector store."

    def add_arguments(self, parser):
        parser.add_argument("--if-stale", action="store_true", help="Only rebuild when the content has changed")

    def handle(self, *args, if_stale=False, **options):
        if build_index(if_stale=if_stale):
            self.stdout.write(self.style.SUCCESS("Reference corpus synced"))
        else:
            self.stdout.write("Reference corpus already up to date")
