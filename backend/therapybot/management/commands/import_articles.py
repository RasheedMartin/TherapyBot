from django.core.management.base import BaseCommand

from therapybot.ai import build_index
from therapybot.articles import import_medlineplus
from therapybot.models import KnowledgeArticle


class Command(BaseCommand):
    help = "Import or refresh MedlinePlus mental-health articles, then rebuild the retrieval index."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty", action="store_true", help="Only import when there are no articles yet (used on boot)"
        )

    def handle(self, *args, if_empty=False, **options):
        if if_empty and KnowledgeArticle.objects.exists():
            self.stdout.write("Articles already imported")
            return
        articles = import_medlineplus()
        for article in articles:
            self.stdout.write(f"  {article.title}  ({len(article.body)} chars)  {article.url}")
        self.stdout.write(f"Imported {len(articles)} article(s)")
        build_index()
        self.stdout.write(self.style.SUCCESS("Index rebuilt"))
