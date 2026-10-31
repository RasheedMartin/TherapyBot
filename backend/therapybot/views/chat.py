"""Companion conversations: messages, streaming replies, risk handling and running summaries."""

import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.response import Response

from therapybot import ai, between_sessions
from therapybot.models import (
    Conversation,
    Message,
    Plan,
    PlanStep,
    SavedProvider,
)
from therapybot.serializers import (
    ConversationDetailSerializer,
    ConversationSerializer,
    MessageSerializer,
    SendMessageSerializer,
)
from therapybot.views.common import VERIFIED, ChatThrottle, get_profile

logger = logging.getLogger(__name__)


def user_context(user) -> str:
    """What the bot should know about the user beyond this conversation: profile, therapy, plans, care search."""
    parts = [get_profile(user).chat_context(), between_sessions.companion_context(user)]

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
            origin = " (from their therapist)" if plan.assigned_by_id else ""
            plan_lines.append(f"- {plan.title}{origin}: {step.title} ({progress})")
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
    # Risk is shared with the client's therapists whatever else they've chosen (disclosed at consent)
    notified = between_sessions.flag_chat_risk(conversation.user, user_msg, risk) if risk != "none" else False
    return {
        "conversation": ConversationSerializer(conversation).data,
        "messages": MessageSerializer([user_msg, bot_msg], many=True).data,
        "care_team_notified": notified,
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
