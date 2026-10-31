"""Clinical records: sessions and the documents in a client's record. Clinical text is encrypted at rest."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from therapybot.fields import EncryptedJSONField, EncryptedTextField


class Session(models.Model):
    class Modality(models.TextChoices):
        CBT = "cbt", "CBT"
        DBT = "dbt", "DBT"
        ACT = "act", "ACT"
        INTEGRATIVE = "integrative", "Integrative / other"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    client = models.ForeignKey("Client", on_delete=models.CASCADE, related_name="sessions")
    therapist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sessions")
    date = models.DateField()
    modality = models.CharField(max_length=12, choices=Modality.choices, default=Modality.INTEGRATIVE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Session {self.date} ({self.client})"


class ClinicalDocument(models.Model):
    """
    A document in someone's clinical record. Either part of a practice's record for a client (`client`,
    usually written by the therapist), or a client's own upload (`owner`, e.g. an after-visit summary
    they want explained), which their therapists can see once linked.
    """

    class DocType(models.TextChoices):
        CLIENT_UPLOAD = "client_upload", "Uploaded by the client"
        PROGRESS_NOTE = "progress_note", "Progress note"
        TRANSCRIPT = "transcript", "Session transcript"
        INTAKE = "intake", "Intake"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINAL = "final", "Final"  # signed by the therapist, or a client upload

    client = models.ForeignKey(
        "Client", on_delete=models.CASCADE, null=True, blank=True, related_name="documents"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="session_notes"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=DocType.choices, default=DocType.CLIENT_UPLOAD)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.FINAL)
    title = models.CharField(max_length=120)
    session_date = models.DateField(null=True, blank=True)
    text = EncryptedTextField(max_length=20000)
    # Client uploads: {"summary", "key_points", "terms", "homework", "questions"}
    explanation = EncryptedJSONField(default=dict)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Signed documents are never edited; corrections are new documents that amend them
    amends = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="amendments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-session_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(client__isnull=False) | Q(owner__isnull=False), name="document_belongs_to_someone"
            )
        ]

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


class TreatmentPlan(models.Model):
    """Goals → objectives → interventions for one client. AI drafts start as drafts; the therapist signs."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    client = models.ForeignKey("Client", on_delete=models.CASCADE, related_name="treatment_plans")
    therapist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    modality = models.CharField(max_length=12, choices=Session.Modality.choices, default=Session.Modality.INTEGRATIVE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    problem_summary = EncryptedTextField(blank=True)
    ai_generated = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Treatment plan for {self.client} ({self.status})"


class TreatmentGoal(models.Model):
    plan = models.ForeignKey(TreatmentPlan, on_delete=models.CASCADE, related_name="goals")
    text = EncryptedTextField()
    # Where in the record this goal came from: [{"label", "document_id", "session_date", ...}]
    evidence = models.JSONField(default=list, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class TreatmentObjective(models.Model):
    goal = models.ForeignKey(TreatmentGoal, on_delete=models.CASCADE, related_name="objectives")
    text = EncryptedTextField()
    measure = models.CharField(max_length=200, blank=True)  # how progress is judged, e.g. "GAD-7 below 10"
    interventions = models.JSONField(default=list, blank=True)  # e.g. ["Cognitive restructuring", ...]
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
