from django.core.management.base import BaseCommand

from therapybot.reminders import send_due_reminders


class Command(BaseCommand):
    help = "Send daily plan reminder emails that are due. Run every 15 minutes (e.g. a Railway cron service)."

    def handle(self, *args, **options):
        sent = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder email(s)"))
