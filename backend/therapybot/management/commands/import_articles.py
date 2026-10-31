from django.core.management.base import BaseCommand

from therapybot.ai import build_index
from therapybot.articles import import_medlineplus


class Command(BaseCommand):
    help = "Import or refresh MedlinePlus mental-health articles, then rebuild the retrieval index."

    def handle(self, *args, **options):
        articles = import_medlineplus()
        for article in articles:
            self.stdout.write(f"  {article.title}  ({len(article.body)} chars)  {article.url}")
        self.stdout.write(f"Imported {len(articles)} article(s)")
        build_index()
        self.stdout.write(self.style.SUCCESS("Index rebuilt"))
