"""Screening results and risk flags."""

from rest_framework import serializers

from therapybot.clinical.instruments import INSTRUMENTS
from therapybot.models import RiskFlag, Screening, ScreeningAssignment, ScreeningTemplate


class ScreeningSerializer(serializers.ModelSerializer):
    responses = serializers.JSONField(read_only=True)  # stored encrypted
    instrument_name = serializers.SerializerMethodField()

    class Meta:
        model = Screening
        fields = ("id", "instrument", "instrument_name", "responses", "total", "severity", "administered_on",
                  "source", "created_at")

    def get_instrument_name(self, screening):
        if screening.template_id:
            return screening.template.name
        standard = INSTRUMENTS.get(screening.instrument)
        return standard.name if standard else screening.instrument


class ScreeningAssignmentSerializer(serializers.ModelSerializer):
    """A check-in sent to a client, as the therapist sees it."""

    instrument_name = serializers.SerializerMethodField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)

    class Meta:
        model = ScreeningAssignment
        fields = ("id", "instrument", "instrument_name", "repeat", "note", "due_on", "active", "last_completed_on",
                  "created_at")
        read_only_fields = ("active", "last_completed_on", "created_at")
        extra_kwargs = {"due_on": {"required": False}}

    def get_instrument_name(self, assignment):
        if assignment.template_id:
            return assignment.template.name
        standard = INSTRUMENTS.get(assignment.instrument)
        return standard.name if standard else assignment.instrument


class ScreeningInputSerializer(serializers.Serializer):
    instrument = serializers.CharField(max_length=20)  # "phq9", "gad7" or "t<template id>"
    responses = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=100))
    administered_on = serializers.DateField(required=False)


class ScreeningTemplateSerializer(serializers.ModelSerializer):
    """A practice's own questionnaire. Questions and scale can't change once it has results."""

    key = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()

    class Meta:
        model = ScreeningTemplate
        fields = ("id", "key", "name", "prompt", "items", "options", "bands", "risk_item", "risk_min", "archived",
                  "results", "created_at", "updated_at")
        read_only_fields = ("archived", "created_at", "updated_at")

    def get_key(self, template):
        return f"t{template.pk}"

    def get_results(self, template):
        return template.results.count()

    def validate_items(self, items):
        if not isinstance(items, list) or not 1 <= len(items) <= 40:
            raise serializers.ValidationError("Add between 1 and 40 questions.")
        cleaned = [str(i).strip()[:300] for i in items]
        if any(not i for i in cleaned):
            raise serializers.ValidationError("Questions can't be empty.")
        return cleaned

    def validate_options(self, options):
        if not isinstance(options, list) or not 2 <= len(options) <= 11:
            raise serializers.ValidationError("An answer scale has 2 to 11 choices.")
        try:
            cleaned = [{"value": int(o["value"]), "label": str(o["label"]).strip()[:60]} for o in options]
        except (KeyError, TypeError, ValueError):
            raise serializers.ValidationError("Each answer needs a number and a label.")
        values = [o["value"] for o in cleaned]
        if values != sorted(set(values)) or values[0] < 0 or values[-1] > 100 or any(not o["label"] for o in cleaned):
            raise serializers.ValidationError("Answer values must be unique, increasing, 0 to 100, and labelled.")
        return cleaned

    def validate_bands(self, bands):
        try:
            cleaned = [{"min": int(b["min"]), "label": str(b["label"]).strip()[:40]} for b in bands or []]
        except (KeyError, TypeError, ValueError):
            raise serializers.ValidationError("Each band needs a starting score and a label.")
        mins = [b["min"] for b in cleaned]
        if mins != sorted(set(mins)) or any(not b["label"] for b in cleaned):
            raise serializers.ValidationError("Bands must start at increasing scores and have labels.")
        return cleaned

    def validate(self, data):
        items = data.get("items", getattr(self.instance, "items", []))
        options = data.get("options", getattr(self.instance, "options", []))
        risk_item = data.get("risk_item", getattr(self.instance, "risk_item", None))
        if risk_item is not None and risk_item >= len(items):
            raise serializers.ValidationError({"risk_item": "Pick one of the questions."})
        risk_min = data.get("risk_min", getattr(self.instance, "risk_min", 1))
        if risk_item is not None and options and risk_min not in {o["value"] for o in options}:
            raise serializers.ValidationError({"risk_min": "Pick one of the answers."})
        if self.instance and self.instance.results.exists() and {"items", "options"} & set(data) and (
                data.get("items", self.instance.items) != self.instance.items
                or data.get("options", self.instance.options) != self.instance.options):
            raise serializers.ValidationError(
                {"items": "This template has results, so its questions and answers are locked. Duplicate it to change them."})
        return data


class RiskFlagSerializer(serializers.ModelSerializer):
    client_id = serializers.IntegerField(source="client.pk", read_only=True)
    client_name = serializers.CharField(source="client.display_name", read_only=True)

    class Meta:
        model = RiskFlag
        fields = ("id", "client_id", "client_name", "level", "source_type", "reason", "created_at",
                  "acknowledged_at")
