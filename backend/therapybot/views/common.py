"""Shared permissions, throttles and helpers for the API views."""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from therapybot.models import (
    Profile,
)
from therapybot.verification import (
    IsEmailVerified,
)

logger = logging.getLogger(__name__)


VERIFIED = [IsAuthenticated, IsEmailVerified]


class AuthThrottle(ScopedRateThrottle):
    scope = "auth"


class ChatThrottle(ScopedRateThrottle):
    scope = "chat"


def get_profile(user) -> Profile:
    # Accounts created before profiles existed get one on first use
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile
