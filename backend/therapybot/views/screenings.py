"""Screenings (therapist-entered or client self-report) and the therapist's risk-flag inbox."""

from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from therapybot import audit
from therapybot.clinical import checkins
from therapybot.clinical.instruments import INSTRUMENTS, get_instrument
from therapybot.clinical.screenings import SAFETY_MESSAGE, record_screening, screening_trends
from therapybot.models import (
    CareRelationship,
    Client,
    Practice,
    RiskFlag,
    Screening,
    ScreeningAssignment,
    ScreeningTemplate,
)
from therapybot.permissions import authorize_client, is_verified_therapist
from therapybot.serializers import (
    therapist_display_name,
    RiskFlagSerializer,
    ScreeningAssignmentSerializer,
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
    if request.method == "DELETE" or request.data.get("archived") is True:
        template.assignments.filter(active=True).update(active=False)  # clients can't complete an archived one
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


def _record(request, client, source, data=None):
    serializer = ScreeningInputSerializer(data=request.data if data is None else data)
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
    if request.data.get("assignment") is not None:
        return _complete_checkin(request)
    client = authorize_client(request.user, request.data.get("client"), "screening.self_report", request=request)
    if not client.relationships.filter(status=CareRelationship.Status.ACTIVE).exists():
        raise Http404("Client not found")
    response = _record(request, client, Screening.Source.SELF_REPORT)
    if response.status_code == 201 and response.data["flagged"]:
        response.data["support_message"] = SAFETY_MESSAGE
    return response


def _complete_checkin(request):
    """A check-in the therapist sent: recorded as a self-report, then the assignment moves to its next date."""
    assignment = checkins.visible(ScreeningAssignment.objects.filter(
        pk=request.data.get("assignment"), client__user=request.user, due_on__lte=timezone.localdate(),
    )).select_related("client__practice").first()
    if assignment is None:
        return Response({"detail": "This check-in isn't open right now."}, status=status.HTTP_404_NOT_FOUND)
    response = _record(request, assignment.client, Screening.Source.SELF_REPORT,
                       {"instrument": assignment.instrument, "responses": request.data.get("responses")})
    if response.status_code == 201:
        checkins.complete(assignment)
        if response.data["flagged"]:
            response.data["support_message"] = SAFETY_MESSAGE
    return response


@api_view(["GET"])
@permission_classes(VERIFIED)
def my_checkins(request):
    """Check-ins the client's therapists sent: due ones (with the questions) and the next upcoming date."""
    assignments = checkins.visible(ScreeningAssignment.objects.filter(client__user=request.user)).select_related(
        "client__practice", "assigned_by__profile")
    today = timezone.localdate()
    result = []
    for a in assignments:
        instrument = get_instrument(a.instrument, a.client.practice, include_archived=False)
        if instrument is None:
            continue
        relationship = a.client.relationships.filter(therapist=a.assigned_by).values_list("pk", flat=True).first()
        result.append({
            "id": a.id, "due": a.due_on <= today, "due_on": a.due_on, "repeat": a.repeat, "note": a.note,
            "therapist_name": therapist_display_name(a.assigned_by), "relationship": relationship,
            "last_completed_on": a.last_completed_on, "instrument": instrument.as_dict(),
        })
    return Response(result)


@api_view(["GET", "POST"])
@permission_classes(THERAPIST)
def client_checkins(request, pk):
    """Check-ins sent to this client. POST {instrument, repeat, due_on?, note?} sends one and emails them."""
    client = authorize_client(request.user, pk, "checkin.view" if request.method == "GET" else "checkin.assign",
                              request=request)
    if request.method == "GET":
        assignments = client.screening_assignments.select_related("template").order_by("-active", "due_on")[:20]
        return Response(ScreeningAssignmentSerializer(assignments, many=True).data)
    if client.user_id is None:
        return Response({"detail": "Invite this client to TherapyBot first so they can complete check-ins."},
                        status=status.HTTP_400_BAD_REQUEST)
    serializer = ScreeningAssignmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    instrument = get_instrument(data["instrument"], client.practice, include_archived=False)
    if instrument is None:
        return Response({"instrument": ["Choose a screening from your list."]}, status=status.HTTP_400_BAD_REQUEST)
    today = timezone.localdate()
    due_on = data.get("due_on") or today
    if due_on < today:
        return Response({"due_on": ["Choose today or a later date."]}, status=status.HTTP_400_BAD_REQUEST)
    if client.screening_assignments.filter(instrument=data["instrument"], active=True).exists():
        return Response({"instrument": [f"{instrument.name} is already sent to this client. Stop it first to change it."]},
                        status=status.HTTP_400_BAD_REQUEST)
    template_id = int(data["instrument"][1:]) if instrument.custom else None
    assignment = serializer.save(client=client, assigned_by=request.user, template_id=template_id, due_on=due_on)
    audit.record(request.user, "checkin.assign", request=request, client=client, obj=assignment,
                 instrument=assignment.instrument, repeat=assignment.repeat)
    emailed = due_on == today and checkins.notify(assignment)
    return Response({**ScreeningAssignmentSerializer(assignment).data, "emailed": emailed},
                    status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes(THERAPIST)
def client_checkin_detail(request, pk, assignment_id):
    """Stop sending a check-in. Results already completed stay in the record."""
    client = authorize_client(request.user, pk, "checkin.stop", request=request)
    assignment = client.screening_assignments.filter(pk=assignment_id).first()
    if assignment is None:
        raise Http404("Check-in not found")
    assignment.active = False
    assignment.save(update_fields=["active"])
    audit.record(request.user, "checkin.stop", request=request, client=client, obj=assignment)
    return Response(status=status.HTTP_204_NO_CONTENT)


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
