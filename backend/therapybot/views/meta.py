"""Health check and public settings."""

import logging

from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from therapybot.serializers import (
    THERAPY_TYPES,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    try:
        connection.ensure_connection()
    except Exception:
        logger.exception("Health check: database unavailable")
        return Response({"status": "error", "database": False}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"status": "ok", "database": True})


@api_view(["GET"])
@permission_classes([AllowAny])
def public_config(request):
    """Settings the frontend needs before sign-in."""
    return Response({"google_client_id": settings.GOOGLE_CLIENT_ID or None})


@api_view(["GET"])
@permission_classes([AllowAny])
def therapy_types(request):
    return Response(THERAPY_TYPES)
