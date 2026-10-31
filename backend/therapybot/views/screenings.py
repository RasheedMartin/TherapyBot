"""Screenings (therapist-entered or client self-report) and the therapist's risk-flag inbox."""

from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from therapybot import audit
from therapybot.clinical.instruments import INSTRUMENTS
from therapybot.clinical.screenings import SAFETY_MESSAGE, record_screening, screening_trends
from therapybot.models import CareRelationship, Client, RiskFlag, Screening
from therapybot.permissions import authorize_client
from therapybot.serializers import RiskFlagSerializer, ScreeningInputSerializer, ScreeningSerializer
from therapybot.views.common import VERIFIED
from therapybot.views.practice import THERAPIST


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def instruments(request):
    return Response([i.as_dict() for i in INSTRUMENTS.values()])


def _record(request, client, source):
    serializer = ScreeningInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        screening, flag = record_screening(
            client=client, instrument_key=data["instrument"], responses=data["responses"],
            administered_on=data.get("administered_on"), source=source, entered_by=request.user, request=request,
        )
    except ValueError as e:
        return Response({"responses": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
    return Response({**ScreeningSerializer(screening).data, "flagged": flag is not None}, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes(THERAPIST)
def client_screenings(request, pk):
    """GET: all screenings plus the latest trend per instrument. POST: enter a result from session."""
    client = authorize_client(request.user, pk, "screening.view" if request.method == "GET" else "screening.enter",
                              request=request)
    if request.method == "POST":
        return _record(request, client, Screening.Source.CLINICIAN)
    return Response({"screenings": ScreeningSerializer(Screening.objects.filter(client=client), many=True).data,
                     "trends": screening_trends(client)})


@api_view(["GET", "POST"])
@permission_classes(VERIFIED)
def my_screenings(request):
    """
    The client's side. GET: their past results. POST {client, ...}: a self-report into the record that a
    therapist they're connected with keeps (client = that Client record's id, which is theirs).
    """
    if request.method == "GET":
        records = Client.objects.filter(user=request.user)
        return Response(ScreeningSerializer(Screening.objects.filter(client__in=records), many=True).data)
    client = authorize_client(request.user, request.data.get("client"), "screening.self_report", request=request)
    if not client.relationships.filter(status=CareRelationship.Status.ACTIVE).exists():
        raise Http404("Client not found")
    response = _record(request, client, Screening.Source.SELF_REPORT)
    if response.status_code == 201 and response.data["flagged"]:
        response.data["support_message"] = SAFETY_MESSAGE
    return response


@api_view(["GET"])
@permission_classes(THERAPIST)
def risk_flags(request):
    """Open flags (and the last 30 days of acknowledged ones) for clients currently in this therapist's care."""
    active_clients = Client.objects.filter(relationships__therapist=request.user,
                                           relationships__status=CareRelationship.Status.ACTIVE)
    flags = RiskFlag.objects.filter(client__in=active_clients).select_related("client").exclude(
        acknowledged_at__lt=timezone.now() - timezone.timedelta(days=30)
    )
    audit.record(request.user, "risk_flag.list", request=request, count=flags.count())
    return Response(RiskFlagSerializer(flags, many=True).data)


@api_view(["POST"])
@permission_classes(THERAPIST)
def acknowledge_risk_flag(request, flag_id):
    flag = RiskFlag.objects.select_related("client").filter(pk=flag_id).first()
    if flag is None:
        raise Http404("Flag not found")
    authorize_client(request.user, flag.client_id, "risk_flag.acknowledge", request=request)
    if flag.acknowledged_at is None:
        flag.acknowledged_at, flag.acknowledged_by = timezone.now(), request.user
        flag.save(update_fields=["acknowledged_at", "acknowledged_by"])
    return Response(RiskFlagSerializer(flag).data)
