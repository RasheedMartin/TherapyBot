"""Find care: provider search and the user's shortlist."""

import logging

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from therapybot import providers
from therapybot.models import (
    PlanStep,
    SavedProvider,
    StepCheckIn,
)
from therapybot.serializers import (
    SavedProviderSerializer,
)
from therapybot.views.common import VERIFIED

logger = logging.getLogger(__name__)


class ProviderThrottle(ScopedRateThrottle):
    scope = "providers"


@api_view(["GET"])
@permission_classes(VERIFIED)
@throttle_classes([ProviderThrottle])
def provider_search(request):
    zip_code = (request.query_params.get("zip") or "").strip()
    if not (len(zip_code) == 5 and zip_code.isdigit()):
        return Response({"zip": ["Enter a 5-digit US ZIP code."]}, status=status.HTTP_400_BAD_REQUEST)
    types = [t for t in (request.query_params.get("types") or "").split(",") if t]
    try:
        return Response(providers.search_providers(zip_code, types))
    except providers.ProviderSearchError as e:
        return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class SavedProviderListCreate(generics.ListCreateAPIView):
    serializer_class = SavedProviderSerializer
    permission_classes = VERIFIED
    pagination_class = None

    def get_queryset(self):
        return SavedProvider.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # Saving the same provider twice just returns the existing entry
        existing = self.get_queryset().filter(npi=request.data.get("npi")).first()
        if existing:
            return Response(self.get_serializer(existing).data)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavedProviderDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SavedProviderSerializer
    permission_classes = VERIFIED

    def get_queryset(self):
        return SavedProvider.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        saved = serializer.save()
        if saved.status in (SavedProvider.Status.CONTACTED, SavedProvider.Status.SCHEDULED):
            # Reaching out completes any open "contact a therapist" step in the user's plans
            open_steps = PlanStep.objects.filter(
                plan__user=self.request.user,
                plan__archived=False,
                action=PlanStep.Action.FIND_CARE,
                frequency=PlanStep.Frequency.ONCE,
                check_ins__isnull=True,
            )
            for step in open_steps:
                StepCheckIn.objects.get_or_create(step=step, date=timezone.localdate())
