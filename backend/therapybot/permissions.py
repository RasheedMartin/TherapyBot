"""
Who may see which client's data. Every client-scoped read or write goes through `authorize_client`,
which also writes the audit log, so access rules live in one place.
"""

from django.http import Http404
from rest_framework.permissions import BasePermission

from therapybot import audit
from therapybot.models import CareRelationship, Client, Profile


def is_verified_therapist(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(
        profile and profile.role == Profile.Role.THERAPIST and profile.npi_status == Profile.NpiStatus.VERIFIED
    )


class IsVerifiedTherapist(BasePermission):
    """Therapist account whose NPI has been verified (automatically or by manual review)."""

    message = "This is available to therapists once their NPI is verified."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_verified_therapist(request.user))


def active_relationship(user, client: Client) -> CareRelationship | None:
    return CareRelationship.objects.filter(
        client=client, therapist=user, status=CareRelationship.Status.ACTIVE
    ).first()


def authorize_client(user, client_id, purpose: str, *, request=None, allow_invited: bool = False) -> Client:
    """
    Return the client if `user` may access their record for `purpose`, else raise Http404 (so callers
    can't probe which clients exist). Allowed: a verified therapist with an active relationship, or
    (with allow_invited) the therapist who sent a pending invite. Every attempt is audited.
    """
    client = Client.objects.select_related("practice").filter(pk=client_id).first()
    allowed = False
    if client is not None and is_verified_therapist(user):
        statuses = [CareRelationship.Status.ACTIVE] + ([CareRelationship.Status.INVITED] if allow_invited else [])
        allowed = CareRelationship.objects.filter(client=client, therapist=user, status__in=statuses).exists()
    audit.record(user, purpose, request=request, client=client, denied=not allowed, client_id=str(client_id))
    if not allowed:
        raise Http404("Client not found")
    return client
