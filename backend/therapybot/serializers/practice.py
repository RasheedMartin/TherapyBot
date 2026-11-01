"""Therapist practices, client records and care relationships."""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from therapybot.models import CareRelationship, Client


class TherapistRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    npi = serializers.CharField(max_length=10)
    practice_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    confirm_age = serializers.BooleanField()
    accept_terms = serializers.BooleanField()

    def validate_npi(self, value):
        from therapybot.providers import npi_checksum_ok

        value = value.strip()
        if not npi_checksum_ok(value):
            raise serializers.ValidationError("Enter a valid 10-digit NPI.")
        return value


class ClientInviteSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120)
    email = serializers.EmailField()


class RelationshipSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = CareRelationship
        fields = ("id", "status", "invited_at", "consented_at", "ended_at",
                  "share_checkins", "share_chat_summaries", "share_raw_chat")


class ClientSerializer(serializers.ModelSerializer):
    """A client as their therapist sees them in the roster."""

    relationship = serializers.SerializerMethodField()
    has_account = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ("id", "display_name", "email", "has_account", "created_at", "relationship")

    def get_has_account(self, client):
        return client.user_id is not None

    def get_relationship(self, client):
        therapist = self.context["request"].user
        rel = client.relationships.filter(therapist=therapist).exclude(status="ended").first()
        return RelationshipSummarySerializer(rel).data if rel else None


class CareTeamSerializer(serializers.ModelSerializer):
    """A care relationship as the client sees it: who can see what."""

    therapist_name = serializers.SerializerMethodField()
    practice_name = serializers.CharField(source="client.practice.name", read_only=True)
    next_session = serializers.SerializerMethodField()
    next_session_time = serializers.SerializerMethodField()

    class Meta:
        model = CareRelationship
        fields = ("id", "therapist_name", "practice_name", "status", "invited_at", "consented_at", "ended_at",
                  "share_checkins", "share_chat_summaries", "share_raw_chat", "next_session",
                  "next_session_time")
        read_only_fields = ("status", "invited_at", "consented_at", "ended_at")

    def get_therapist_name(self, rel):
        return therapist_display_name(rel.therapist)

    def _next(self, rel):
        """The client's next scheduled session with this therapist, for their home page."""
        if rel.status != CareRelationship.Status.ACTIVE:
            return None
        return (
            rel.client.sessions.filter(therapist=rel.therapist, status="scheduled", date__gte=timezone.localdate())
            .order_by("date", "start_time").first()
        )

    def get_next_session(self, rel):
        session = self._next(rel)
        return session.date.isoformat() if session else None

    def get_next_session_time(self, rel):
        session = self._next(rel)
        return session.start_time.strftime("%H:%M:%S") if session and session.start_time else None


def therapist_display_name(user: User) -> str:
    profile = getattr(user, "profile", None)
    details = (profile.npi_details or {}) if profile else {}
    name = user.get_full_name() or details.get("registry_name") or user.username
    credential = details.get("credential", "")
    return f"{name}, {credential}" if credential else name
