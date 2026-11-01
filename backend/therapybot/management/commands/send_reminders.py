from django.core.management.base import BaseCommand

from therapybot.clinical.checkins import send_due_notices
from therapybot.reminders import send_due_reminders


class Command(BaseCommand):
    help = (
        "Send daily plan reminder emails and therapist check-in notices that are due. "
        "Run every 15 minutes (e.g. a Railway cron service)."
    )

    def handle(self, *args, **options):
        sent = send_due_reminders()
        notices = send_due_notices()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder email(s) and {notices} check-in notice(s)"))
