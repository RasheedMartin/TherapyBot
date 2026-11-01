"""Plans, check-ins, calendar export and feed, and reminder-email links."""

import logging
import secrets
from datetime import date, timedelta
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from therapybot import ai, reminders
from therapybot.calendar_feed import render_calendar
from therapybot.models import (
    CareRelationship,
    Conversation,
    Plan,
    PlanStep,
    Profile,
    Session,
    StepCheckIn,
)
from therapybot.serializers import (
    PlanSerializer,
    PlanStepSerializer,
    therapist_display_name,
)
from therapybot.verification import (
    is_email_verified,
)
from therapybot.views.common import VERIFIED, AuthThrottle, ChatThrottle, get_profile

logger = logging.getLogger(__name__)


class PlanListCreate(generics.ListCreateAPIView):
    serializer_class = PlanSerializer
    permission_classes = VERIFIED

    def get_queryset(self):
        return Plan.objects.filter(user=self.request.user).prefetch_related("steps__check_ins")


class PlanDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PlanSerializer
    permission_classes = VERIFIED

    def get_queryset(self):
        return Plan.objects.filter(user=self.request.user).prefetch_related("steps__check_ins")


def clean_ai_steps(raw_steps, limit: int) -> list[dict]:
    """Validate model-proposed plan steps like user input, dropping anything malformed."""
    steps = []
    for step in (raw_steps if isinstance(raw_steps, list) else [])[:limit]:
        if not isinstance(step, dict):
            continue
        candidate = PlanStepSerializer(data={
            "title": str(step.get("title", ""))[:160],
            "details": str(step.get("details") or "")[:1000],
            "frequency": step.get("frequency") if step.get("frequency") in PlanStep.Frequency.values else "daily",
            "weekday": step.get("weekday"),
            "time_of_day": step.get("time_of_day"),
            "action": step.get("action") if step.get("action") in PlanStep.Action.values else "",
        })
        if candidate.is_valid():
            valid = candidate.validated_data
            time_of_day = valid.get("time_of_day")
            steps.append({
                "title": valid["title"],
                "details": valid.get("details", ""),
                "frequency": valid["frequency"],
                "weekday": valid.get("weekday"),
                "time_of_day": time_of_day.strftime("%H:%M") if time_of_day else None,
                "action": valid.get("action", ""),
            })
    return steps


@api_view(["POST"])
@permission_classes(VERIFIED)
@throttle_classes([ChatThrottle])
def draft_plan(request):
    """Draft (but don't save) a plan from a conversation, for the user to review and edit."""
    conversation = get_object_or_404(Conversation, pk=request.data.get("conversation"), user=request.user)
    recent = list(conversation.messages.order_by("-created_at", "-id")[: settings.CHAT_HISTORY_TURNS * 2])
    if not recent:
        return Response({"detail": "Chat a little first, then we can turn it into a plan."}, status=400)
    history = [(m.role, m.content) for m in reversed(recent)]
    try:
        draft = ai.draft_plan(history, conversation.therapy_type, get_profile(request.user).chat_context())
    except Exception:
        logger.exception("Plan draft failed for conversation %s", conversation.pk)
        return Response({"detail": "Couldn't draft a plan right now. Please try again."}, status=503)

    steps = clean_ai_steps(draft.get("steps"), limit=5)
    if not steps:
        return Response({"detail": "Couldn't draft a plan right now. Please try again."}, status=503)
    return Response({
        "title": str(draft.get("title") or "My plan")[:120],
        "summary": str(draft.get("summary") or "")[:1000],
        "conversation": conversation.pk,
        "steps": steps,
    })


@api_view(["POST", "DELETE"])
@permission_classes(VERIFIED)
def step_check_in(request, pk):
    """POST marks a step done for a date (default today); DELETE un-marks it."""
    step = get_object_or_404(PlanStep, pk=pk, plan__user=request.user)
    try:
        day = date.fromisoformat(request.data.get("date") or timezone.localdate().isoformat())
    except ValueError:
        return Response({"date": ["Use YYYY-MM-DD."]}, status=status.HTTP_400_BAD_REQUEST)
    if request.method == "POST":
        StepCheckIn.objects.get_or_create(step=step, date=day)
    else:
        StepCheckIn.objects.filter(step=step, date=day).delete()
    step.plan.save(update_fields=["updated_at"])
    return Response(PlanSerializer(step.plan, context={"request": request}).data)


@api_view(["GET"])
@permission_classes(VERIFIED)
def plan_calendar(request, pk):
    """Download a plan as a one-off .ics file."""
    plan = get_object_or_404(Plan, pk=pk, user=request.user)
    body = render_calendar(plan.title, plan.steps.prefetch_related("check_ins").select_related("plan"))
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="therapybot-plan.ics"'
    return response


def _feed_urls(request, profile):
    if not profile.calendar_token:
        return {"enabled": False, "discreet": profile.calendar_discreet}
    https_url = request.build_absolute_uri(f"/api/calendar/{profile.calendar_token}.ics")
    webcal_url = "webcal://" + https_url.split("://", 1)[1]
    return {
        "enabled": True,
        "discreet": profile.calendar_discreet,
        "url": https_url,
        "webcal_url": webcal_url,
        "google_url": f"https://calendar.google.com/calendar/render?cid={quote(webcal_url, safe='')}",
    }


@api_view(["GET", "POST", "PATCH", "DELETE"])
@permission_classes(VERIFIED)
def calendar_feed_settings(request):
    """
    GET: current feed links. POST: create (or rotate) the secret feed link.
    PATCH {discreet}: toggle generic event titles. DELETE: turn the feed off.
    """
    profile = get_profile(request.user)
    if request.method == "POST":
        profile.calendar_token = secrets.token_urlsafe(32)
    elif request.method == "PATCH":
        profile.calendar_discreet = bool(request.data.get("discreet"))
    elif request.method == "DELETE":
        profile.calendar_token = None
    if request.method != "GET":
        profile.save(update_fields=["calendar_token", "calendar_discreet"])
    return Response(_feed_urls(request, profile))


CALENDAR_PAST_DAYS = 60


def _initials(name: str) -> str:
    return "".join(f"{part[0].upper()}." for part in name.split()[:3] if part) or "Client"


def calendar_sessions(profile) -> list:
    """
    Sessions for someone's calendar feed, with titles. Therapists see clients by initials only, since feeds
    sync into third-party calendars; clients see their therapist's name. Only active care relationships.
    """
    since = timezone.localdate() - timedelta(days=CALENDAR_PAST_DAYS)
    active = CareRelationship.Status.ACTIVE
    if profile.role == Profile.Role.THERAPIST:
        sessions = Session.objects.filter(
            therapist=profile.user, date__gte=since,
            client__relationships__therapist=profile.user, client__relationships__status=active,
        ).select_related("client").distinct()
        return [(s, f"Session · {_initials(s.client.display_name)}") for s in sessions]
    sessions = Session.objects.filter(
        client__user=profile.user, date__gte=since,
        client__relationships__therapist=F("therapist"), client__relationships__status=active,
    ).select_related("therapist__profile").distinct()
    return [(s, f"Therapy session · {therapist_display_name(s.therapist)}") for s in sessions]


@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def calendar_feed(request, token):
    """Subscribed calendars fetch this without logging in; the unguessable token is the credential."""
    profile = Profile.objects.filter(calendar_token=token).select_related("user").first()
    if profile is None or not is_email_verified(profile.user):
        return HttpResponse(status=404)
    steps = (
        PlanStep.objects.filter(plan__user=profile.user, plan__archived=False)
        .select_related("plan")
        .prefetch_related("check_ins")
    )
    sessions = calendar_sessions(profile)
    name = "TherapyBot sessions" if profile.role == Profile.Role.THERAPIST else "TherapyBot plans"
    body = render_calendar(name, steps, discreet=profile.calendar_discreet, sessions=sessions)
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Cache-Control"] = "private, max-age=900"
    return response


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([AuthThrottle])
def quick_check_in(request):
    """GET previews the step (safe for link scanners); POST marks it done."""
    token = request.query_params.get("t") or request.data.get("t") or ""
    try:
        step_id, day = reminders.read_check_in_token(token)
        step = PlanStep.objects.select_related("plan").get(pk=step_id)
    except (signing.BadSignature, PlanStep.DoesNotExist, KeyError, ValueError):
        return Response(
            {"detail": "This link has expired. Open TherapyBot to check in."}, status=status.HTTP_400_BAD_REQUEST
        )
    if request.method == "POST":
        StepCheckIn.objects.get_or_create(step=step, date=day)
    done = StepCheckIn.objects.filter(step=step, date=day).exists()
    return Response({"step": step.title, "plan": step.plan.title, "date": day.isoformat(), "done": done})


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([AuthThrottle])
def unsubscribe_reminders(request):
    """Turns reminders off. Also serves RFC 8058 one-click unsubscribe from mail clients."""
    token = request.query_params.get("t") or request.data.get("t") or ""
    try:
        user_id = reminders.read_unsubscribe_token(token)
    except signing.BadSignature:
        return Response({"detail": "This link isn't valid."}, status=status.HTTP_400_BAD_REQUEST)
    Profile.objects.filter(user_id=user_id).update(reminders_enabled=False)
    return Response({"detail": "Daily reminders are off."})
