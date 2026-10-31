"""The therapist side: registering with an NPI, the client roster, and inviting or ending client relationships."""

import logging

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from therapybot import audit, invites, providers
from therapybot.models import CareRelationship, Client, Practice, PracticeMembership, Profile
from therapybot.permissions import IsVerifiedTherapist, authorize_client
from therapybot.serializers import ClientInviteSerializer, ClientSerializer, TherapistRegisterSerializer, UserSerializer
from therapybot.verification import IsEmailVerified, send_verification_email
from therapybot.views.common import AuthThrottle

logger = logging.getLogger(__name__)

THERAPIST = [IsAuthenticated, IsEmailVerified, IsVerifiedTherapist]


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register_therapist(request):
    """Create a therapist account and their practice. The NPI is checked now; unclear cases go to review."""
    serializer = TherapistRegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if not (data["confirm_age"] and data["accept_terms"]):
        return Response({"accept_terms": ["Please accept the Terms and Privacy Policy to continue."]}, status=400)
    errors = {}
    if User.objects.filter(username__iexact=data["username"]).exists():
        errors["username"] = ["That username is already taken."]
    if User.objects.filter(email__iexact=data["email"]).exists():
        errors["email"] = ["An account with that email already exists."]
    if Profile.objects.filter(npi=data["npi"], role=Profile.Role.THERAPIST).exists():
        errors["npi"] = ["That NPI is already registered. Contact support if this is you."]
    candidate = User(username=data["username"], email=data["email"], first_name=data["first_name"],
                     last_name=data["last_name"])
    try:
        validate_password(data["password"], user=candidate)
    except DjangoValidationError as e:
        errors["password"] = list(e.messages)
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    npi_status, details = providers.verify_therapist_npi(data["npi"], data["first_name"], data["last_name"])
    now = timezone.now()
    with transaction.atomic():
        user = User.objects.create_user(
            username=data["username"], email=data["email"].lower(), password=data["password"],
            first_name=data["first_name"], last_name=data["last_name"],
        )
        Profile.objects.create(
            user=user, role=Profile.Role.THERAPIST, npi=data["npi"], npi_status=npi_status, npi_details=details,
            npi_verified_at=now if npi_status == Profile.NpiStatus.VERIFIED else None,
            age_confirmed_at=now, terms_accepted_at=now,
        )
        practice = Practice.objects.create(
            name=data.get("practice_name") or f"{data['first_name']} {data['last_name']}'s practice"
        )
        PracticeMembership.objects.create(practice=practice, user=user, role=PracticeMembership.Role.OWNER)
    audit.record(user, "therapist.register", request=request, practice=practice, npi_status=npi_status)
    send_verification_email(user)
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


def _therapist_practice(user) -> Practice:
    membership = user.practice_memberships.select_related("practice").order_by("created_at").first()
    return membership.practice


@api_view(["GET", "POST"])
@permission_classes(THERAPIST)
def clients(request):
    """GET: the therapist's roster (active and invited). POST: create a client record and email an invite."""
    if request.method == "GET":
        roster = (
            Client.objects.filter(relationships__therapist=request.user)
            .exclude(relationships__status=CareRelationship.Status.ENDED)
            .distinct()
            .select_related("practice")
        )
        audit.record(request.user, "client.list", request=request, count=len(roster))
        return Response(ClientSerializer(roster, many=True, context={"request": request}).data)

    serializer = ClientInviteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    practice = _therapist_practice(request.user)
    email = serializer.validated_data["email"].lower()
    existing = Client.objects.filter(practice=practice, email__iexact=email).first()
    if existing and existing.relationships.filter(therapist=request.user).exclude(status="ended").exists():
        return Response({"email": ["You've already invited this client."]}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        client = existing or Client.objects.create(
            practice=practice, display_name=serializer.validated_data["display_name"], email=email,
            created_by=request.user,
        )
        relationship = CareRelationship.objects.create(client=client, therapist=request.user)
    audit.record(request.user, "client.invite", request=request, client=client, obj=relationship)
    invites.send_invite(relationship)
    return Response(ClientSerializer(client, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes(THERAPIST)
def client_detail(request, pk):
    client = authorize_client(request.user, pk, "client.view", request=request, allow_invited=True)
    return Response(ClientSerializer(client, context={"request": request}).data)


@api_view(["POST"])
@permission_classes(THERAPIST)
@throttle_classes([AuthThrottle])
def resend_invite(request, pk):
    client = authorize_client(request.user, pk, "client.resend_invite", request=request, allow_invited=True)
    relationship = client.relationships.filter(therapist=request.user, status=CareRelationship.Status.INVITED).first()
    if relationship is None:
        return Response({"detail": "This client has already accepted."}, status=status.HTTP_400_BAD_REQUEST)
    invites.send_invite(relationship)
    return Response({"detail": f"Invitation sent again to {client.email}."})


@api_view(["POST"])
@permission_classes(THERAPIST)
def end_relationship(request, pk):
    """The therapist ends care (or withdraws a pending invite). Their access stops immediately."""
    client = authorize_client(request.user, pk, "relationship.end", request=request, allow_invited=True)
    relationship = client.relationships.filter(therapist=request.user).exclude(status="ended").first()
    relationship.status = CareRelationship.Status.ENDED
    relationship.ended_at, relationship.ended_by = timezone.now(), request.user
    relationship.save(update_fields=["status", "ended_at", "ended_by"])
    return Response(status=status.HTTP_204_NO_CONTENT)
