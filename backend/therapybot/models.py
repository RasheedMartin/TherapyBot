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


class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    # A conversation started from session notes keeps them in context
    note = models.ForeignKey("SessionNote", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")
    title = models.CharField(max_length=120, blank=True)
    therapy_type = models.CharField(max_length=80, default="General Therapy")
    # Running summary of older messages that no longer fit in the model's history window
    summary = models.TextField(blank=True)
    summarized_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation {self.pk}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user"
        ASSISTANT = "assistant"

    class Risk(models.TextChoices):
        NONE = "none"
        ELEVATED = "elevated"
        IMMINENT = "imminent"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    is_crisis = models.BooleanField(default=False)
    # Safety assessment of the user's message (copied onto the reply so the UI can react)
    risk_level = models.CharField(max_length=10, choices=Risk.choices, default=Risk.NONE)
    # App feature to offer under an assistant reply ("find_care", "plan", "notes"), chosen by the screener
    suggested_action = models.CharField(max_length=20, blank=True)
    # Further reading surfaced with an assistant reply: [{"title", "url", "source"}]
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"


class SavedProvider(models.Model):
    """A provider from the directory that the user shortlisted, with their own outreach status."""

    class Status(models.TextChoices):
        SAVED = "saved", "Saved"
        CONTACTED = "contacted", "Contacted"
        WAITLIST = "waitlist", "On waitlist"
        SCHEDULED = "scheduled", "Appointment scheduled"
        NOT_A_FIT = "not_a_fit", "Not a fit"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_providers")
    npi = models.CharField(max_length=10)
    details = models.JSONField()  # snapshot of the directory record (name, address, phone, ...)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SAVED)
    notes = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["user", "npi"], name="unique_saved_provider")]

    def __str__(self):
        return f"{self.details.get('name', self.npi)} ({self.get_status_display()})"


class Plan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plans")
    title = models.CharField(max_length=120)
    summary = models.TextField(max_length=1000, blank=True)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name="plans"
    )
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["archived", "-updated_at"]

    def __str__(self):
        return self.title


class PlanStep(models.Model):
    class Action(models.TextChoices):
        NONE = "", "None"
        FIND_CARE = "find_care", "Find care"

    class Frequency(models.TextChoices):
        ONCE = "once", "Once"
        DAILY = "daily", "Every day"
        WEEKDAYS = "weekdays", "Weekdays"
        WEEKLY = "weekly", "Weekly"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="steps")
    title = models.CharField(max_length=160)
    details = models.TextField(max_length=1000, blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.DAILY)
    weekday = models.PositiveSmallIntegerField(null=True, blank=True)  # 0=Monday, for weekly steps
    time_of_day = models.TimeField(null=True, blank=True)
    # Links the step to an app feature, e.g. a "call a therapist" step opens the shortlist
    action = models.CharField(max_length=20, choices=Action.choices, default=Action.NONE, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def is_due_on(self, day: datetime.date) -> bool:
        """Mirrors isDueOn in the frontend (components/plans/schedule.ts)."""
        if self.frequency == self.Frequency.DAILY:
            return True
        if self.frequency == self.Frequency.WEEKDAYS:
            return day.weekday() < 5
        if self.frequency == self.Frequency.WEEKLY:
            return day.weekday() == self.weekday
        dates = [c.date for c in self.check_ins.all()]
        return not dates or day in dates


class StepCheckIn(models.Model):
    step = models.ForeignKey(PlanStep, on_delete=models.CASCADE, related_name="check_ins")
    date = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["step", "date"], name="unique_step_check_in")]


class KnowledgeArticle(models.Model):
    """Reference material for retrieval, from public-domain or licensed sources. Editable in the admin."""

    title = models.CharField(max_length=200)
    url = models.URLField(unique=True)
    source = models.CharField(max_length=80)  # e.g. "MedlinePlus"
    body = models.TextField()  # Markdown with ## section headings
    active = models.BooleanField(default=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} ({self.source})"


class SessionNote(models.Model):
    """Notes or an after-visit summary from the user's own clinician, with a plain-language explanation."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_notes")
    title = models.CharField(max_length=120)
    session_date = models.DateField(null=True, blank=True)
    original_text = models.TextField(max_length=20000)
    # {"summary", "key_points": [...], "terms": [{"term", "meaning"}], "homework": [...steps], "questions": [...]}
    explanation = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-session_date", "-created_at"]

    def __str__(self):
        return self.title

    def chat_context(self) -> str:
        """The notes' explanation, for a conversation started from them."""
        e = self.explanation or {}
        lines = [f"\nThis conversation is about notes from their clinician ({self.title}). Plain-language summary:",
                 e.get("summary", "")]
        if e.get("homework"):
            lines.append("Assigned homework: " + "; ".join(h["title"] for h in e["homework"]))
        lines.append("Help them understand and act on these notes. Don't contradict their clinician; "
                     "suggest they ask their clinician about anything uncertain.")
        return "\n".join(lines)
