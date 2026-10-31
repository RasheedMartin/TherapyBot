"""Screening results and risk flags."""

from rest_framework import serializers

from therapybot.models import RiskFlag, Screening


class ScreeningSerializer(serializers.ModelSerializer):
    responses = serializers.JSONField(read_only=True)  # stored encrypted

    class Meta:
        model = Screening
        fields = ("id", "instrument", "responses", "total", "severity", "administered_on", "source", "created_at")


class ScreeningInputSerializer(serializers.Serializer):
    instrument = serializers.ChoiceField(choices=Screening.Instrument.choices)
    responses = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=3))
    administered_on = serializers.DateField(required=False)


class RiskFlagSerializer(serializers.ModelSerializer):
    client_id = serializers.IntegerField(source="client.pk", read_only=True)
    client_name = serializers.CharField(source="client.display_name", read_only=True)

    class Meta:
        model = RiskFlag
        fields = ("id", "client_id", "client_name", "level", "source_type", "reason", "created_at",
                  "acknowledged_at")
