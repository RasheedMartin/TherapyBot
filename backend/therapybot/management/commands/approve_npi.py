"""
Approve (or reject) a therapist's NPI after manual review, without the admin:

    python manage.py approve_npi <username>            # approve
    python manage.py approve_npi <username> --reject   # reject
    python manage.py approve_npi --pending             # list accounts waiting for review
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from therapybot import audit
from therapybot.models import Profile


class Command(BaseCommand):
    help = "Approve or reject a therapist's NPI after manual review."

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?")
        parser.add_argument("--reject", action="store_true", help="Reject instead of approve")
        parser.add_argument("--pending", action="store_true", help="List therapists waiting for review")

    def handle(self, *args, username=None, reject=False, pending=False, **options):
        therapists = Profile.objects.filter(role=Profile.Role.THERAPIST).select_related("user")
        if pending:
            for p in therapists.filter(npi_status=Profile.NpiStatus.NEEDS_REVIEW):
                reason = (p.npi_details or {}).get("reason", "")
                self.stdout.write(f"{p.user.username}  {p.user.get_full_name()}  NPI {p.npi}  {reason}")
            return
        if not username:
            raise CommandError("Give a username, or --pending to list accounts waiting for review")
        profile = therapists.filter(user__username=username).first()
        if profile is None:
            raise CommandError(f"No therapist account named {username!r}")
        if reject:
            profile.npi_status, profile.npi_verified_at = Profile.NpiStatus.REJECTED, None
        else:
            profile.npi_status, profile.npi_verified_at = Profile.NpiStatus.VERIFIED, timezone.now()
        profile.save(update_fields=["npi_status", "npi_verified_at"])
        audit.record(None, "therapist.npi_review", decision="rejected" if reject else "approved",
                     therapist_id=str(profile.user_id))
        self.stdout.write(self.style.SUCCESS(f"{'Rejected' if reject else 'Approved'} NPI for {username}"))
