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
from therapybot.models import CareRelationship, Client, Practice, RiskFlag, Screening, ScreeningTemplate
from therapybot.permissions import authorize_client, is_verified_therapist
from therapybot.serializers import (
    RiskFlagSerializer,
    ScreeningInputSerializer,
    ScreeningSerializer,
    ScreeningTemplateSerializer,
)
from therapybot.views.common import VERIFIED
from therapybot.views.practice import THERAPIST, _therapist_practice


def _practices_for(user):
    """Practices whose templates this person can use: their own practice, or those caring for them as a client."""
    if is_verified_therapist(user):
        return [_therapist_practice(user)]
    return list(Practice.objects.filter(
        clients__user=user, clients__relationships__status=CareRelationship.Status.ACTIVE).distinct())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def instruments(request):
    """Standard instruments, then the practice's own templates (not archived)."""
    templates = ScreeningTemplate.objects.filter(practice__in=_practices_for(request.user), archived=False)
    return Response([i.as_dict() for i in INSTRUMENTS.values()] + [t.as_instrument().as_dict() for t in templates])


@api_view(["GET", "POST"])
@permission_classes(THERAPIST)
def screening_templates(request):
    """The practice's screening templates. POST creates one."""
    practice = _therapist_practice(request.user)
    if request.method == "GET":
        templates = ScreeningTemplate.objects.filter(practice=practice).order_by("archived", "name")
        return Response(ScreeningTemplateSerializer(templates, many=True).data)
    serializer = ScreeningTemplateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    template = serializer.save(practice=practice, created_by=request.user)
    audit.record(request.user, "screening_template.create", request=request, practice=practice, obj=template)
    return Response(ScreeningTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes(THERAPIST)
def screening_template_detail(request, template_id):
    """Edit a template (questions lock once it has results), or archive it. Results are never deleted."""
    practice = _therapist_practice(request.user)
    template = ScreeningTemplate.objects.filter(practice=practice, pk=template_id).first()
    if template is None:
        raise Http404("Template not found")
    if request.method == "DELETE":
        template.archived = True
        template.save(update_fields=["archived", "updated_at"])
        audit.record(request.user, "screening_template.archive", request=request, practice=practice, obj=template)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = ScreeningTemplateSerializer(template, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    template = serializer.save(archived=bool(request.data.get("archived", template.archived)))
    audit.record(request.user, "screening_template.edit", request=request, practice=practice, obj=template)
    return Response(ScreeningTemplateSerializer(template).data)


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
