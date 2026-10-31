"""User profiles: preferences, consent records, reminders, calendar feed."""

import datetime
import zoneinfo

from django.conf import settings
from django.db import models
from django.utils import timezone as dj_timezone


class Profile(models.Model):
    class SessionFormat(models.TextChoices):
        ANY = "any", "No preference"
        IN_PERSON = "in_person", "In person"
        TELEHEALTH = "telehealth", "Telehealth"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=80, blank=True)
    goals = models.TextField(max_length=1000, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    insurance = models.CharField(max_length=120, blank=True)
    session_format = models.CharField(max_length=12, choices=SessionFormat.choices, default=SessionFormat.ANY)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Private calendar subscription (secret URL token) for plans
    calendar_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    calendar_discreet = models.BooleanField(default=False)
    # Daily email reminder of the day's plan steps, sent at reminder_time in the user's time zone
    timezone = models.CharField(max_length=64, blank=True)  # IANA name, detected by the browser
    reminders_enabled = models.BooleanField(default=False)
    reminder_time = models.TimeField(default=datetime.time(8, 0))
    reminder_last_sent = models.DateField(null=True, blank=True)
    # Consent record captured at sign-up
    age_confirmed_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user}"

    def local_now(self) -> datetime.datetime:
        try:
            tz = zoneinfo.ZoneInfo(self.timezone) if self.timezone else dj_timezone.get_default_timezone()
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            tz = dj_timezone.get_default_timezone()
        return dj_timezone.now().astimezone(tz)

    def chat_context(self) -> str:
        """Details the user chose to share, for personalizing replies."""
        lines = []
        if self.display_name:
            lines.append(f"- They like to be called {self.display_name}.")
        if self.goals:
            lines.append(f"- What they want to work on: {self.goals}")
        if not lines:
            return ""
        return "\nAbout the user (shared by them in their profile; use naturally, don't recite):\n" + "\n".join(lines)
