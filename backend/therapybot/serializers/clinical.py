"""The therapist's view of a client's record: sessions, documents, treatment plans."""

from rest_framework import serializers

from therapybot.models import ClinicalDocument, Session, TreatmentGoal, TreatmentObjective, TreatmentPlan


def _name(user) -> str:
    return (user.get_full_name() or user.username) if user else ""


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ("id", "date", "modality", "status", "created_at")
        read_only_fields = ("created_at",)


class ClinicalDocumentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    signed_by_name = serializers.SerializerMethodField()
    editable = serializers.SerializerMethodField()
    text = serializers.CharField(max_length=20000)

    class Meta:
        model = ClinicalDocument
        fields = ("id", "title", "doc_type", "status", "session", "session_date", "text", "author_name",
                  "signed_at", "signed_by_name", "amends", "editable", "created_at", "updated_at")
        read_only_fields = ("status", "signed_at", "amends", "created_at", "updated_at")

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
        fields = ("id", "title", "doc_type", "status", "session", "session_date", "signed_at", "created_at")


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
        fields = ("id", "modality", "status", "problem_summary", "ai_generated", "signed_at", "goals",
                  "created_at", "updated_at")
        read_only_fields = ("status", "ai_generated", "signed_at", "created_at", "updated_at")

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
