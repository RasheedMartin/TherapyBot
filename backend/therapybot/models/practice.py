"""Therapist practices, their clients, the consented relationships between them, and the access audit log."""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Practice(models.Model):
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PracticeMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        THERAPIST = "therapist", "Therapist"
        ADMIN = "admin", "Practice admin"  # reserved: administrative staff, no clinical access yet

    practice = models.ForeignKey(Practice, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="practice_memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.THERAPIST)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["practice", "user"], name="unique_practice_member")]

    def __str__(self):
        return f"{self.user} @ {self.practice} ({self.role})"


class Client(models.Model):
    """
    A practice's record for one person. It can exist before the person has an account (the therapist
    invites them); `user` is set when they accept. One person can be a client of several practices.
    """

    practice = models.ForeignKey(Practice, on_delete=models.CASCADE, related_name="clients")
    display_name = models.CharField(max_length=120)
    email = models.EmailField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="client_records"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["practice", "user"], condition=Q(user__isnull=False), name="one_client_record_per_practice"
            )
        ]

    def __str__(self):
        return f"{self.display_name} ({self.practice})"


class CareRelationship(models.Model):
    """
    A therapist's access to a client, granted by the client. Risk flags are always shared while active
    (disclosed when the client accepts); the other scopes are the client's choice.
    """

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="relationships")
    therapist = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="care_relationships"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INVITED)
    invited_at = models.DateTimeField(auto_now_add=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # What the client agreed to share between sessions (changeable by the client at any time)
    share_checkins = models.BooleanField(default=True)
    share_chat_summaries = models.BooleanField(default=True)
    share_raw_chat = models.BooleanField(default=False)

    class Meta:
        ordering = ["-invited_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "therapist"],
                condition=~Q(status="ended"),
                name="one_open_relationship_per_client_and_therapist",
            )
        ]

    def __str__(self):
        return f"{self.therapist} → {self.client} ({self.status})"


class AuditEvent(models.Model):
    """
    Append-only record of who accessed or generated what, for which client. Never store clinical content
    or other PHI in `metadata`: identifiers and counts only.
    """

    class Outcome(models.TextChoices):
        ALLOWED = "allowed"
        DENIED = "denied"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_events"
    )
    action = models.CharField(max_length=60)  # e.g. "client.view", "client.invite", "relationship.accept"
    outcome = models.CharField(max_length=10, choices=Outcome.choices, default=Outcome.ALLOWED)
    practice = models.ForeignKey(Practice, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    object_type = models.CharField(max_length=40, blank=True)
    object_id = models.CharField(max_length=40, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_id} {self.action} ({self.outcome})"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Audit events are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit events are append-only")
