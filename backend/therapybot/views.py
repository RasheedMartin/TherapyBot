import json
import logging
import secrets
from datetime import date, timedelta
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import connection, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from therapybot import ai, providers, reminders
from therapybot.calendar_feed import render_calendar
from therapybot.models import (
    Conversation,
    Message,
    Plan,
    PlanStep,
    Profile,
    SavedProvider,
    SessionNote,
    StepCheckIn,
)
from therapybot.serializers import (
    THERAPY_TYPES,
    ChangePasswordSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    MessageSerializer,
    PlanSerializer,
    PlanStepSerializer,
    ProfileSerializer,
    RegisterSerializer,
    SavedProviderSerializer,
    SendMessageSerializer,
    SessionNoteListSerializer,
    SessionNoteSerializer,
    UserSerializer,
)

from therapybot.verification import (
    IsEmailVerified,
    email_verification_token,
    is_email_verified,
    send_verification_email,
)

logger = logging.getLogger(__name__)

# Features that need a confirmed email address
VERIFIED = [IsAuthenticated, IsEmailVerified]


class AuthThrottle(ScopedRateThrottle):
    scope = "auth"


class ChatThrottle(ScopedRateThrottle):
    scope = "chat"


# --- Health / meta -----------------------------------------------------------


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


# --- Accounts ----------------------------------------------------------------


@api_view(["GET"])
def current_user(request):
    return Response(UserSerializer(request.user).data)


def user_context(user) -> str:
    """What the bot should know about the user beyond this conversation: profile, plans, care search."""
    parts = [get_profile(user).chat_context()]

    today = timezone.localdate()
    week_ago = today - timedelta(days=6)
    plan_lines = []
    for plan in Plan.objects.filter(user=user, archived=False).prefetch_related("steps__check_ins")[:3]:
        for step in plan.steps.all()[:5]:
            dates = {c.date for c in step.check_ins.all()}
            if step.frequency == PlanStep.Frequency.ONCE:
                progress = "done" if dates else "not done yet"
            else:
                progress = f"done {sum(week_ago <= d <= today for d in dates)} of the last 7 days"
                progress += ", done today" if today in dates else ", not yet today"
            plan_lines.append(f"- {plan.title}: {step.title} ({progress})")
    if plan_lines:
        parts.append(
            "\nTheir current plan (check in on it only when it fits naturally; celebrate effort, never scold):\n"
            + "\n".join(plan_lines)
        )

    saved = list(SavedProvider.objects.filter(user=user).values_list("status", flat=True))
    if saved:
        counts = {label: saved.count(value) for value, label in SavedProvider.Status.choices if saved.count(value)}
        summary = ", ".join(f"{n} {label.lower()}" for label, n in counts.items())
        parts.append(f"\nThey are looking for a therapist: {len(saved)} on their shortlist ({summary}).")
    return "".join(parts)


def get_profile(user) -> Profile:
    # Accounts created before profiles existed get one on first use
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


@api_view(["GET", "PATCH"])
def profile(request):
    instance = get_profile(request.user)
    if request.method == "GET":
        return Response(ProfileSerializer(instance).data)
    serializer = ProfileSerializer(instance, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if serializer.context.get("email_changed"):
        send_verification_email(instance.user)  # request.user still holds the old address
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def verify_email(request):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(request.data.get("uid") or "")))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is None or not email_verification_token.check_token(user, request.data.get("token") or ""):
        return Response(
            {"detail": "This verification link is invalid or has expired. Sign in to request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    profile = get_profile(user)
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=["email_verified_at"])
    return Response({"detail": "Email verified."})


@api_view(["POST"])
@throttle_classes([AuthThrottle])
def resend_verification(request):
    if is_email_verified(request.user):
        return Response({"detail": "Your email is already verified."})
    send_verification_email(request.user)
    return Response({"detail": f"We sent a new link to {request.user.email}."})


@api_view(["POST"])
@throttle_classes([AuthThrottle])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data["new_password"])
    request.user.save()
    return Response({"detail": "Password updated."})


@api_view(["GET"])
def export_data(request):
    """Everything we store about the user, as a downloadable JSON file."""
    user = request.user
    payload = {
        "exported_at": timezone.now().isoformat(),
        "account": UserSerializer(user).data,
        "profile": ProfileSerializer(get_profile(user)).data,
        "conversations": ConversationDetailSerializer(
            Conversation.objects.filter(user=user).prefetch_related("messages"), many=True
        ).data,
        "plans": PlanSerializer(Plan.objects.filter(user=user).prefetch_related("steps__check_ins"), many=True).data,
        "saved_providers": SavedProviderSerializer(SavedProvider.objects.filter(user=user), many=True).data,
        "session_notes": SessionNoteSerializer(SessionNote.objects.filter(user=user), many=True).data,
    }
    response = Response(payload)
    response["Content-Disposition"] = 'attachment; filename="therapybot-data.json"'
    return response


@api_view(["POST"])
@throttle_classes([AuthThrottle])
def delete_account(request):
    if request.user.has_usable_password():
        if not request.user.check_password(request.data.get("password") or ""):
            return Response({"password": ["Your password is incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
    elif request.data.get("confirm") != "DELETE":
        return Response({"confirm": ['Type "DELETE" to confirm.']}, status=status.HTTP_400_BAD_REQUEST)
    user_id = request.user.pk
    request.user.delete()  # cascades to profile, conversations and messages
    logger.info("Deleted account %s at the user's request", user_id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register_user(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    send_verification_email(user)
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


RESET_SENT_MESSAGE = "If an account with that email exists, a reset link has been sent."


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def forgot_password(request):
    email = (request.data.get("email") or "").strip()
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Respond identically whether or not the account exists
    for user in User.objects.filter(email__iexact=email, is_active=True):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        try:
            send_mail(
                subject="Reset your TherapyBot password",
                message=(
                    f"Hi {user.username},\n\n"
                    f"We received a request to reset your password. Use the link below to choose a new one:\n\n"
                    f"{reset_url}\n\n"
                    f"If you didn't request this, you can safely ignore this email."
                ),
                from_email=None,
                recipient_list=[user.email],
            )
        except Exception:
            logger.exception("Failed to send password reset email to user %s", user.pk)

    return Response({"detail": RESET_SENT_MESSAGE})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def reset_password(request):
    uid = request.data.get("uid")
    token = request.data.get("token")
    new_password = request.data.get("new_password")

    if not all([uid, token, new_password]):
        return Response({"detail": "uid, token, and new_password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response(
            {"detail": "This reset link is invalid or has expired. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return Response({"new_password": e.messages}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({"detail": "Password reset successful."})


# --- Conversations -----------------------------------------------------------


class ConversationListCreate(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = VERIFIED

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ConversationDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = VERIFIED

    def get_serializer_class(self):
        return ConversationDetailSerializer if self.request.method == "GET" else ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).prefetch_related("messages")


def _prepare_chat(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
    serializer = SendMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    content = serializer.validated_data["content"]

    recent = list(conversation.messages.order_by("-created_at", "-id")[: settings.CHAT_HISTORY_TURNS * 2])
    history = [(m.role, m.content) for m in reversed(recent)]
    context = user_context(request.user)
    if conversation.note:
        context += conversation.note.chat_context()
    if conversation.summary:
        context += f"\nEarlier in this conversation (summary of older messages):\n{conversation.summary}"
    return conversation, content, history, context


SUMMARY_BATCH = 10  # fold older messages into the summary in batches, not on every turn


def update_conversation_summary(conversation):
    """Keep a running summary of messages that have scrolled out of the model's history window."""
    window = settings.CHAT_HISTORY_TURNS * 2
    older = conversation.messages.count() - window
    if older - conversation.summarized_count < SUMMARY_BATCH:
        return
    batch = conversation.messages.order_by("created_at", "id")[conversation.summarized_count : older]
    try:
        conversation.summary = ai.summarize_conversation(conversation.summary, [(m.role, m.content) for m in batch])
    except Exception:
        logger.warning("Summary update failed for conversation %s", conversation.pk, exc_info=True)
        return
    conversation.summarized_count = older
    conversation.save(update_fields=["summary", "summarized_count"])


def _save_exchange(conversation, content, reply, is_crisis, sources=(), risk="none", action=""):
    with transaction.atomic():
        user_msg = Message.objects.create(
            conversation=conversation, role=Message.Role.USER, content=content, is_crisis=is_crisis, risk_level=risk
        )
        bot_msg = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=reply,
            is_crisis=is_crisis,
            risk_level=risk,
            suggested_action=action if risk == "none" else "",
            sources=[] if risk != "none" else list(sources)[:2],
        )
        if not conversation.title:
            conversation.title = content if len(content) <= 60 else content[:57].rstrip() + "…"
        conversation.save()
    return {
        "conversation": ConversationSerializer(conversation).data,
        "messages": MessageSerializer([user_msg, bot_msg], many=True).data,
    }


AI_UNAVAILABLE = "TherapyBot is having trouble responding right now. Please try again in a moment."


@api_view(["POST"])
@permission_classes(VERIFIED)
@throttle_classes([ChatThrottle])
def send_message(request, pk):
    conversation, content, history, user_context = _prepare_chat(request, pk)
    sources, assessment = [], {}
    try:
        reply, is_crisis = ai.therapy_chat(
            content, conversation.therapy_type, history, user_context, sources, assessment=assessment
        )
    except Exception:
        logger.exception("AI response failed for conversation %s", conversation.pk)
        return Response({"detail": AI_UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    risk = assessment.get("risk", "imminent" if is_crisis else "none")
    data = _save_exchange(conversation, content, reply, is_crisis, sources, risk, assessment.get("next_step", ""))
    update_conversation_summary(conversation)
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes(VERIFIED)
@throttle_classes([ChatThrottle])
def stream_message(request, pk):
    """
    Stream the reply as newline-delimited JSON events:
    {"type": "delta", "text": ...}* then {"type": "done", "conversation": ..., "messages": [...]}
    or {"type": "error", "detail": ...}. Nothing is saved unless the reply completes.
    """
    conversation, content, history, user_context = _prepare_chat(request, pk)

    def event(payload):
        return json.dumps(payload) + "\n"

    def events():
        parts, sources, assessment = [], [], {}
        try:
            for delta in ai.therapy_chat_stream(
                content, conversation.therapy_type, history, user_context, sources, assessment=assessment
            ):
                parts.append(delta)
                yield event({"type": "delta", "text": delta})
        except Exception:
            logger.exception("AI stream failed for conversation %s", conversation.pk)
            yield event({"type": "error", "detail": AI_UNAVAILABLE})
            return
        reply = "".join(parts).strip()
        if not reply:
            yield event({"type": "error", "detail": AI_UNAVAILABLE})
            return
        risk = assessment.get("risk", "imminent" if ai.is_crisis_message(content) else "none")
        action = assessment.get("next_step", "")
        yield event({"type": "done", **_save_exchange(conversation, content, reply, risk == "imminent", sources, risk, action)})
        # After the reply is delivered, so it never delays the user
        update_conversation_summary(conversation)

    response = StreamingHttpResponse(events(), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # stop proxies from buffering the stream
    return response


# --- Find care ---------------------------------------------------------------


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


# --- Plans -------------------------------------------------------------------


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
    body = render_calendar("TherapyBot plans", steps, discreet=profile.calendar_discreet)
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Cache-Control"] = "private, max-age=900"
    return response


# --- Sign in with Google -----------------------------------------------------


def _unique_username(email: str) -> str:
    base = "".join(c for c in email.split("@")[0] if c.isalnum() or c in "._-")[:30] or "user"
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
@throttle_classes([AuthThrottle])
def google_sign_in(request):
    """
    Exchange a Google ID token for our JWTs. New users must also send confirm_age and accept_terms;
    without them the response is 400 with consent_required so the app can ask.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
    from rest_framework_simplejwt.tokens import RefreshToken

    if not settings.GOOGLE_CLIENT_ID:
        return Response({"detail": "Google sign-in isn't configured."}, status=status.HTTP_404_NOT_FOUND)
    try:
        claims = id_token.verify_oauth2_token(
            request.data.get("credential") or "", google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        return Response({"detail": "Google sign-in failed. Please try again."}, status=status.HTTP_400_BAD_REQUEST)
    if not claims.get("email") or not claims.get("email_verified"):
        return Response({"detail": "Your Google account's email isn't verified."}, status=status.HTTP_400_BAD_REQUEST)

    email = claims["email"].lower()
    user = User.objects.filter(email__iexact=email).first()
    created = user is None
    now = timezone.now()
    if created:
        if not (request.data.get("confirm_age") is True and request.data.get("accept_terms") is True):
            return Response(
                {"consent_required": True, "detail": "Please confirm you're 18+ and accept the terms."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User(username=_unique_username(email), email=email)
        user.set_unusable_password()
        user.save()
        Profile.objects.create(
            user=user,
            display_name=(claims.get("given_name") or "")[:80],
            email_verified_at=now,
            age_confirmed_at=now,
            terms_accepted_at=now,
        )
    else:
        # Google has proven ownership of this address, so it counts as verified
        profile = get_profile(user)
        if not profile.email_verified_at:
            profile.email_verified_at = now
            profile.save(update_fields=["email_verified_at"])
    if not user.is_active:
        return Response({"detail": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh), "created": created})


# --- Reminder email links (no sign-in; signed tokens) -------------------------


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


# --- Session notes -----------------------------------------------------------

MAX_NOTE_CHARS = 20000


def _extract_upload_text(upload) -> str:
    name = (upload.name or "").lower()
    if upload.size > 5 * 1024 * 1024:
        raise ValueError("That file is too large. Please upload a file under 5 MB.")
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(upload)
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:30])
        except (PdfReadError, ValueError):
            raise ValueError("Couldn't read that PDF. Try copying and pasting the text instead.")
        if len(text.strip()) < 20:
            raise ValueError("That PDF looks like a scanned image, so there's no text to read. Please paste the text.")
        return text
    if name.endswith((".txt", ".md")):
        return upload.read().decode("utf-8", errors="replace")
    raise ValueError("Upload a PDF or text file, or paste your notes.")


class SessionNoteListCreate(generics.ListCreateAPIView):
    permission_classes = VERIFIED

    def get_queryset(self):
        return SessionNote.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return SessionNoteListSerializer if self.request.method == "GET" else SessionNoteSerializer

    def get_throttles(self):
        return [ChatThrottle()] if self.request.method == "POST" else super().get_throttles()

    def create(self, request, *args, **kwargs):
        try:
            upload = request.FILES.get("file")
            text = _extract_upload_text(upload) if upload else (request.data.get("text") or "")
        except ValueError as e:
            return Response({"file": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        text = text.strip()
        if len(text) < 20:
            return Response({"text": ["Paste or upload your notes (at least a sentence or two)."]}, status=400)
        if len(text) > MAX_NOTE_CHARS:
            return Response({"text": [f"Notes are limited to {MAX_NOTE_CHARS:,} characters."]}, status=400)

        try:
            raw = ai.explain_notes(text, get_profile(request.user).chat_context())
        except Exception:
            logger.exception("Notes explanation failed for user %s", request.user.pk)
            return Response({"detail": "Couldn't explain these notes right now. Please try again."}, status=503)

        explanation = {
            "summary": str(raw.get("summary", ""))[:2000],
            "key_points": [str(p)[:500] for p in raw.get("key_points", []) if p][:8],
            "terms": [
                {"term": str(t.get("term", ""))[:80], "meaning": str(t.get("meaning", ""))[:500]}
                for t in raw.get("terms", [])
                if isinstance(t, dict) and t.get("term")
            ][:12],
            "homework": clean_ai_steps(raw.get("homework"), limit=8),
            "questions": [str(q)[:300] for q in raw.get("questions", []) if q][:6],
        }
        serializer = SessionNoteSerializer(data={
            "title": (request.data.get("title") or raw.get("title") or "Session notes")[:120],
            "session_date": request.data.get("session_date") or None,
        })
        serializer.is_valid(raise_exception=True)
        note = serializer.save(user=request.user, original_text=text, explanation=explanation)
        return Response(SessionNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class SessionNoteDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionNoteSerializer
    permission_classes = VERIFIED

    def get_queryset(self):
        return SessionNote.objects.filter(user=self.request.user)


@api_view(["POST"])
@permission_classes(VERIFIED)
def discuss_note(request, pk):
    """Start a conversation that has these notes in context."""
    note = get_object_or_404(SessionNote, pk=pk, user=request.user)
    conversation = Conversation.objects.create(
        user=request.user, note=note, title=f"About: {note.title}"[:120], therapy_type="General Therapy"
    )
    return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)
