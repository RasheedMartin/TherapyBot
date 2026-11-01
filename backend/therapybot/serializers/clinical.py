"""The therapist's view of a client's record: sessions, documents, treatment plans."""

from django.utils import timezone
from rest_framework import serializers

from therapybot.models import ClinicalDocument, Session, TreatmentGoal, TreatmentObjective, TreatmentPlan


def _name(user) -> str:
    return (user.get_full_name() or user.username) if user else ""


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ("id", "date", "start_time", "duration_minutes", "modality", "status", "created_at")
        read_only_fields = ("created_at",)

    def validate_duration_minutes(self, value):
        if not 10 <= value <= 240:
            raise serializers.ValidationError("Sessions are between 10 and 240 minutes.")
        return value


class ScheduledSessionSerializer(SessionSerializer):
    """A session on the therapist's schedule, across clients."""

    client_id = serializers.IntegerField(source="client.pk", read_only=True)
    client_name = serializers.CharField(source="client.display_name", read_only=True)

    class Meta(SessionSerializer.Meta):
        fields = SessionSerializer.Meta.fields + ("client_id", "client_name")


class ClinicalDocumentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    signed_by_name = serializers.SerializerMethodField()
    editable = serializers.SerializerMethodField()
    text = serializers.CharField(max_length=20000)

    class Meta:
        model = ClinicalDocument
        fields = ("id", "title", "doc_type", "status", "session", "session_date", "text", "author_name",
                  "signed_at", "signed_by_name", "amends", "editable", "imported_from", "summary_of", "created_at",
                  "updated_at")
        read_only_fields = ("status", "signed_at", "amends", "imported_from", "summary_of", "created_at", "updated_at")

    def get_author_name(self, doc):
        return _name(doc.author)

    def get_signed_by_name(self, doc):
        return _name(doc.signed_by)

    def get_editable(self, doc):
        return doc.status == ClinicalDocument.Status.DRAFT and doc.client_id is not None

    def validate_doc_type(self, value):
        if value == ClinicalDocument.DocType.CLIENT_UPLOAD:
            raise serializers.ValidationError("Client uploads come from the client.")
        return value


class DocumentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalDocument
        fields = ("id", "title", "doc_type", "status", "session", "session_date", "signed_at", "imported_from",
                  "created_at")


class TreatmentObjectiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = TreatmentObjective
        fields = ("text", "measure", "interventions")


class TreatmentGoalSerializer(serializers.ModelSerializer):
    objectives = TreatmentObjectiveSerializer(many=True)

    class Meta:
        model = TreatmentGoal
        fields = ("text", "evidence", "objectives")
        read_only_fields = ("evidence",)


class TreatmentPlanSerializer(serializers.ModelSerializer):
    goals = TreatmentGoalSerializer(many=True)

    class Meta:
        model = TreatmentPlan
        fields = ("id", "modality", "status", "problem_summary", "ai_generated", "signed_at", "share_with_client",
                  "goals", "created_at", "updated_at")
        read_only_fields = ("status", "ai_generated", "signed_at", "share_with_client", "created_at", "updated_at")

    def update(self, plan, validated_data):
        """Replace the goals wholesale; evidence is kept for goals whose text didn't change."""
        goals = validated_data.pop("goals", None)
        plan = super().update(plan, validated_data)
        if goals is not None:
            evidence = {g.text: g.evidence for g in plan.goals.all()}
            plan.goals.all().delete()
            save_goals(plan, [{**g, "evidence": evidence.get(g["text"], [])} for g in goals])
        return plan


def save_goals(plan: TreatmentPlan, goals: list[dict]) -> None:
    for i, goal in enumerate(goals):
        saved = TreatmentGoal.objects.create(plan=plan, text=goal["text"], evidence=goal.get("evidence", []), order=i)
        for j, objective in enumerate(goal.get("objectives", [])):
            TreatmentObjective.objects.create(
                goal=saved, text=objective["text"], measure=objective.get("measure", ""),
                interventions=objective.get("interventions", []), order=j,
            )


class ImportedDocumentSerializer(serializers.Serializer):
    """One reviewed document from an import, as the therapist confirmed it."""

    IMPORTABLE = [ClinicalDocument.DocType.PROGRESS_NOTE, ClinicalDocument.DocType.TRANSCRIPT,
                  ClinicalDocument.DocType.INTAKE, ClinicalDocument.DocType.OTHER]

    title = serializers.CharField(max_length=120)
    doc_type = serializers.ChoiceField(choices=IMPORTABLE)
    session_date = serializers.DateField(allow_null=True, required=False)
    text = serializers.CharField(min_length=20, max_length=20000, trim_whitespace=True)
    filename = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_session_date(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("A note's date can't be in the future.")
        return value
