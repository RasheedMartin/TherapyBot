"""Therapist → client invitations: signed links that let a client review and accept a care relationship."""

import logging

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

from therapybot.models import CareRelationship

logger = logging.getLogger(__name__)

INVITE_SALT = "therapybot.invites"
INVITE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def invite_token(relationship: CareRelationship) -> str:
    return signing.dumps({"r": relationship.pk}, salt=INVITE_SALT, compress=True)


def read_invite_token(token: str) -> CareRelationship | None:
    """The pending relationship this token invites to, or None if it's invalid, expired, or already used."""
    try:
        rel_id = signing.loads(token, salt=INVITE_SALT, max_age=INVITE_MAX_AGE)["r"]
    except (signing.BadSignature, KeyError, TypeError):
        return None
    return (
        CareRelationship.objects.select_related("client__practice", "therapist__profile")
        .filter(pk=rel_id, status=CareRelationship.Status.INVITED)
        .first()
    )


def send_invite(relationship: CareRelationship) -> None:
    from therapybot.serializers import therapist_display_name

    client, therapist = relationship.client, relationship.therapist
    link = f"{settings.FRONTEND_URL}/care-team/invite?t={invite_token(relationship)}"
    try:
        send_mail(
            subject=f"{therapist_display_name(therapist)} invited you to TherapyBot",
            message=(
                f"Hi {client.display_name},\n\n"
                f"{therapist_display_name(therapist)} ({client.practice.name}) has invited you to connect on "
                f"TherapyBot, a companion for the time between your sessions.\n\n"
                f"You'll see exactly what would be shared before you accept, and you can change it any time:\n\n"
                f"{link}\n\n"
                f"If you weren't expecting this, you can ignore this email."
            ),
            from_email=None,
            recipient_list=[client.email],
        )
    except Exception:
        logger.exception("Failed to send invite for relationship %s", relationship.pk)
