"""Email verification: single-use links that expire when the email or verification state changes."""

import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "therapybot.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        profile = getattr(user, "profile", None)
        verified = profile.email_verified_at if profile else None
        return f"{user.pk}{user.email}{verified}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()


def is_email_verified(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.email_verified_at)


def send_verification_email(user) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"
    try:
        send_mail(
            subject="Confirm your TherapyBot email",
            message=(
                f"Hi {user.username},\n\n"
                f"Please confirm your email address to finish setting up your account:\n\n"
                f"{link}\n\n"
                f"If you didn't create a TherapyBot account, you can ignore this email."
            ),
            from_email=None,
            recipient_list=[user.email],
        )
    except Exception:
        logger.exception("Failed to send verification email to user %s", user.pk)


class IsEmailVerified(BasePermission):
    message = "Please verify your email address to continue."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_email_verified(request.user))
