"""The client side of care relationships: reviewing and accepting invites, and controlling what's shared."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from therapybot import audit, invites
from therapybot.models import CareRelationship, Client
from therapybot.serializers import CareTeamSerializer, therapist_display_name
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
@permission_classes(VERIFIED)
@throttle_classes([AuthThrottle])
def accept_invite(request):
    """Link the signed-in client to the therapist, with the sharing choices they made."""
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
