"""The client side of care relationships: reviewing and accepting invites, and controlling what's shared."""

from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from therapybot import audit, invites
from therapybot.models import (
    CareRelationship,
    Client,
    ClinicalDocument,
    Plan,
    Profile,
    Screening,
    Session,
    TreatmentPlan,
)
from therapybot.serializers import CareTeamSerializer, ScreeningSerializer, therapist_display_name
from therapybot.views.common import VERIFIED, AuthThrottle

SHARED_ALWAYS = (
    "Safety alerts: if a message suggests you may be at risk of harming yourself, your therapist sees a flag. "
    "This is not live monitoring; in an emergency call 911, or call or text 988."
)
SCOPES = ("share_checkins", "share_chat_summaries", "share_raw_chat")


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def invite_preview(request):
    """What an invite link offers, so the client can decide before signing in or accepting."""
    relationship = invites.read_invite_token(request.query_params.get("t") or "")
    if relationship is None:
        return Response({"detail": "This invitation is invalid, expired, or already used."}, status=400)
    return Response({
        "therapist_name": therapist_display_name(relationship.therapist),
        "practice_name": relationship.client.practice.name,
        "invited_email": relationship.client.email,
        "always_shared": SHARED_ALWAYS,
        "defaults": {scope: getattr(relationship, scope) for scope in SCOPES},
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def accept_invite(request):
    """
    Link the signed-in client to the therapist, with the sharing choices they made. The invite was emailed
    to this address and the account's email must match, so accepting also verifies the email: a new
    client doesn't have to wait for a second email before connecting.
    """
    relationship = invites.read_invite_token(request.data.get("t") or "")
    if relationship is None:
        return Response({"detail": "This invitation is invalid, expired, or already used."}, status=400)
    client = relationship.client
    # The link went to a specific inbox; accepting from a different account would hand someone else's record over
    if client.email.lower() != (request.user.email or "").lower():
        audit.record(request.user, "relationship.accept", request=request, client=client, obj=relationship,
                     denied=True, reason="email_mismatch")
        return Response(
            {"detail": f"This invitation was sent to {client.email}. Sign in with that account to accept it."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if relationship.therapist_id == request.user.pk:
        return Response({"detail": "You can't accept your own invitation."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if not profile.email_verified_at:
            profile.email_verified_at = timezone.now()
            profile.save(update_fields=["email_verified_at"])
        # If this person is already a client of the practice under another record, keep a single record:
        # move the relationship onto it first, then drop the now-empty placeholder.
        existing = Client.objects.filter(practice=client.practice, user=request.user).exclude(pk=client.pk).first()
        if existing:
            if existing.relationships.filter(therapist=relationship.therapist).exclude(status="ended").exists():
                return Response({"detail": "You're already connected with this therapist."}, status=400)
            placeholder, client = client, existing
            relationship.client = client
            relationship.save(update_fields=["client"])
            if not placeholder.relationships.exists():
                placeholder.delete()
        else:
            client.user = request.user
            client.save(update_fields=["user"])
        for scope in SCOPES:
            if scope in request.data:
                setattr(relationship, scope, bool(request.data[scope]))
        relationship.status = CareRelationship.Status.ACTIVE
        relationship.consented_at = timezone.now()
        relationship.save()
    audit.record(request.user, "relationship.accept", request=request, client=client, obj=relationship,
                 **{scope: getattr(relationship, scope) for scope in SCOPES})
    return Response(CareTeamSerializer(relationship).data)


@api_view(["GET"])
@permission_classes(VERIFIED)
def care_team(request):
    """The client's therapists, current and past, and what each can see."""
    relationships = (
        CareRelationship.objects.filter(client__user=request.user)
        .exclude(status=CareRelationship.Status.INVITED)
        .select_related("therapist__profile", "client__practice")
    )
    return Response(CareTeamSerializer(relationships, many=True).data)


@api_view(["GET"])
@permission_classes(VERIFIED)
def my_sessions(request):
    """
    The client's upcoming sessions with therapists currently in their care, including ones cancelled so a
    cancellation is visible rather than a session silently disappearing.
    """
    today = timezone.localdate()
    sessions = (
        Session.objects.filter(
            client__user=request.user, date__gte=today,
            status__in=[Session.Status.SCHEDULED, Session.Status.CANCELLED],
            client__relationships__therapist=F("therapist"),
            client__relationships__status=CareRelationship.Status.ACTIVE,
        )
        .select_related("therapist__profile").distinct()
        .order_by("date", F("start_time").asc(nulls_first=True))[:12]
    )
    return Response([
        {"id": s.id, "date": s.date, "start_time": s.start_time, "duration_minutes": s.duration_minutes,
         "status": s.status, "therapist_name": therapist_display_name(s.therapist)}
        for s in sessions
    ])


@api_view(["GET"])
@permission_classes(VERIFIED)
def my_summaries(request):
    """Session summaries a therapist currently in the client's care has shared with them, newest first."""
    summaries = (
        ClinicalDocument.objects.filter(
            client__user=request.user, doc_type=ClinicalDocument.DocType.CLIENT_SUMMARY,
            status=ClinicalDocument.Status.FINAL,
            client__relationships__therapist=F("author"),
            client__relationships__status=CareRelationship.Status.ACTIVE,
        )
        .select_related("author__profile").distinct().order_by("-signed_at")[:10]
    )
    return Response([
        {"id": d.id, "session_date": d.session_date, "shared_at": d.signed_at, "text": d.text,
         "therapist_name": therapist_display_name(d.author)}
        for d in summaries
    ])


@api_view(["GET"])
@permission_classes(VERIFIED)
def therapist_overview(request, pk):
    """
    Everything about one therapist in one place, from the client's side: who they are, sessions, completed
    check-ins, homework, and shared summaries and goals. Their private notes are never included. Open check-ins
    come from screenings/checkins/, which carries the questions.
    """
    relationship = get_object_or_404(
        CareRelationship.objects.select_related("therapist__profile", "client__practice"),
        pk=pk, client__user=request.user, status__in=[CareRelationship.Status.ACTIVE, CareRelationship.Status.ENDED],
    )
    therapist, client = relationship.therapist, relationship.client
    profile = getattr(therapist, "profile", None)
    details = (profile.npi_details or {}) if profile else {}
    data = {
        "relationship": CareTeamSerializer(relationship).data,
        "therapist": {"name": therapist_display_name(therapist), "specialty": details.get("taxonomy", ""),
                      "practice_name": client.practice.name},
    }
    if relationship.status != CareRelationship.Status.ACTIVE:
        # After care ends the therapist's shared material goes with them; the client keeps their own results
        return Response(data)

    today = timezone.localdate()
    sessions = client.sessions.filter(therapist=therapist)
    upcoming = sessions.filter(date__gte=today, status__in=[Session.Status.SCHEDULED, Session.Status.CANCELLED]) \
        .order_by("date", F("start_time").asc(nulls_first=True))[:6]
    last = sessions.filter(date__lt=today, status=Session.Status.COMPLETED).order_by("-date").first()

    completed = Screening.objects.filter(client=client, source=Screening.Source.SELF_REPORT) \
        .select_related("template")[:5]

    plan = TreatmentPlan.objects.filter(client=client, therapist=therapist, status=TreatmentPlan.Status.ACTIVE,
                                        share_with_client=True).prefetch_related("goals__objectives").first()
    homework = Plan.objects.filter(user=request.user, assigned_by=therapist, archived=False).prefetch_related("steps")
    summaries = client.documents.filter(author=therapist, doc_type=ClinicalDocument.DocType.CLIENT_SUMMARY,
                                        status=ClinicalDocument.Status.FINAL).order_by("-signed_at")[:10]
    return Response({
        **data,
        "sessions": [
            {"id": s.id, "date": s.date, "start_time": s.start_time, "duration_minutes": s.duration_minutes,
             "status": s.status, "therapist_name": data["therapist"]["name"]} for s in upcoming
        ],
        "last_session": last.date if last else None,
        "sessions_attended": sessions.filter(status=Session.Status.COMPLETED).count(),
        "completed_checkins": [
            {"id": s["id"], "name": s["instrument_name"], "date": s["administered_on"]}
            for s in ScreeningSerializer(completed, many=True).data
        ],
        "goals": [
            {"text": g.text, "objectives": [o.text for o in g.objectives.all()]} for g in plan.goals.all()
        ] if plan else [],
        "homework": [
            {"id": h.id, "title": h.title, "steps": [st.title for st in h.steps.all()]} for h in homework
        ],
        "summaries": [
            {"id": d.id, "session_date": d.session_date, "shared_at": d.signed_at, "text": d.text,
             "therapist_name": data["therapist"]["name"]} for d in summaries
        ],
    })


@api_view(["PATCH"])
@permission_classes(VERIFIED)
def update_sharing(request, pk):
    """The client changes what this therapist can see. Takes effect immediately."""
    relationship = get_object_or_404(
        CareRelationship, pk=pk, client__user=request.user, status=CareRelationship.Status.ACTIVE
    )
    changed = {}
    for scope in SCOPES:
        if scope in request.data:
            changed[scope] = bool(request.data[scope])
            setattr(relationship, scope, changed[scope])
    relationship.save(update_fields=list(changed) or None)
    audit.record(request.user, "relationship.update_sharing", request=request, client=relationship.client,
                 obj=relationship, **changed)
    return Response(CareTeamSerializer(relationship).data)


@api_view(["POST"])
@permission_classes(VERIFIED)
def leave_care(request, pk):
    """The client ends the relationship; the therapist loses access immediately."""
    relationship = get_object_or_404(
        CareRelationship, pk=pk, client__user=request.user, status=CareRelationship.Status.ACTIVE
    )
    relationship.status = CareRelationship.Status.ENDED
    relationship.ended_at, relationship.ended_by = timezone.now(), request.user
    relationship.save(update_fields=["status", "ended_at", "ended_by"])
    audit.record(request.user, "relationship.end", request=request, client=relationship.client, obj=relationship)
    return Response(status=status.HTTP_204_NO_CONTENT)
