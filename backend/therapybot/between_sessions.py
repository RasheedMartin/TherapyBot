"""
The link between a client's companion and their care team: what the companion knows of the therapist's
plan, safety flags raised from chat, and the conversation summaries a client chooses to share.
Clients without an active therapist relationship get none of this and the companion works as before.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from therapybot import llm
from therapybot.models import (
    CareRelationship,
    Client,
    Conversation,
    Message,
    RiskFlag,
    Session,
    TreatmentPlan,
)
from therapybot.rag import RetrievedChunk

logger = logging.getLogger(__name__)

CHAT_FLAG_DEDUPE = timedelta(hours=24)
DEFAULT_WINDOW_DAYS = 14
MAX_SHARED_CONVERSATIONS = 5
SUMMARY_MESSAGES = 40
CHAT_FLAG_REASONS = {
    "elevated": "Companion chat: a message suggested possible risk of self-harm",
    "imminent": "Companion chat: a message suggested immediate risk of self-harm",
}
LEVEL_RANK = {"elevated": 1, "imminent": 2}

CARE_SUMMARY_PROMPT = """You summarize a client's between-session conversation with a self-help companion app, for the client's own therapist, who the client has chosen to share this with.
- Third person, they/them, plain prose, at most 120 words. No headings or lists.
- Cover what the client brought up, what they tried or planned (including any homework), what helped or didn't, and anything they may want to raise in session.
- Report only what the conversation shows. No diagnoses, no clinical interpretation, no advice to the therapist.
- If the client said anything suggesting self-harm, suicide, or being better off dead or gone, quote their words
  briefly. Never describe what they did NOT say about risk (no "did not mention a plan", "no current thoughts");
  a missing statement is not a denial. If the companion asked about safety and they didn't answer, say so.
- If nothing about risk came up, don't mention risk at all.
Reply with the summary text only."""


def active_relationships(user):
    """The client's current therapists, across every practice that keeps a record for them."""
    if user is None or not user.is_authenticated:
        return CareRelationship.objects.none()
    return CareRelationship.objects.filter(
        client__user=user, status=CareRelationship.Status.ACTIVE
    ).select_related("client", "therapist__profile")


def _therapist_name(user) -> str:
    from therapybot.serializers import therapist_display_name

    return therapist_display_name(user)


def companion_context(user) -> str:
    """What the companion should know about the client's therapy, so between-session support follows it."""
    relationships = list(active_relationships(user))
    if not relationships:
        return ""
    names = ", ".join(dict.fromkeys(_therapist_name(r.therapist) for r in relationships))
    clients = [r.client for r in relationships]
    lines = [f"\nThey are working with a therapist ({names}) and use TherapyBot between sessions."]

    upcoming = (
        Session.objects.filter(client__in=clients, status=Session.Status.SCHEDULED, date__gte=timezone.localdate())
        .order_by("date").first()
    )
    if upcoming:
        lines.append(f"Next session: {upcoming.date:%A %B} {upcoming.date.day}.")

    goals = []
    for plan in TreatmentPlan.objects.filter(client__in=clients, status=TreatmentPlan.Status.ACTIVE).prefetch_related(
        "goals__objectives"
    ):
        for goal in plan.goals.all()[:3]:
            goals.append(f"- {goal.text}")
            goals.extend(f"  - {o.text}" for o in goal.objectives.all()[:3])
    if goals:
        lines.append("Goals from the treatment plan they and their therapist agreed on:\n" + "\n".join(goals))

    sharing = []
    if any(r.share_chat_summaries for r in relationships):
        sharing.append("summaries of conversations they haven't marked private")
    if any(r.share_checkins for r in relationships):
        sharing.append("their plan check-ins")
    lines.append(
        "How to use this: support the work they're doing in therapy. Encourage practicing assigned homework "
        "(steps marked 'from their therapist') and connect what they share to these goals when it fits. Don't "
        "change or add to their therapist's plan, don't second-guess it, and suggest they bring bigger questions "
        "or setbacks to their next session. You are not their therapist."
    )
    lines.append(
        "If they ask what their therapist sees: safety alerts always"
        + (f", plus {' and '.join(sharing)}" if sharing else "")
        + ". Their therapist does not read chats live."
    )
    return "\n".join(lines)


# --- Safety flags from chat ---------------------------------------------------------------------------


def flag_chat_risk(user, message: Message, level: str) -> bool:
    """
    Raise a flag for each active therapist when a chat message shows risk. Shared regardless of the
    client's other choices (disclosed when they accepted). Returns True if any therapist will see one.
    """
    if level not in CHAT_FLAG_REASONS:
        return False
    relationships = list(active_relationships(user))
    notified = False
    for client in {r.client_id: r.client for r in relationships}.values():
        notified = True
        recent = RiskFlag.objects.filter(
            client=client, source_type=RiskFlag.SourceType.CHAT, acknowledged_at__isnull=True,
            created_at__gte=timezone.now() - CHAT_FLAG_DEDUPE,
        )
        # One open flag per day is enough to prompt follow-up, unless the risk has gone up
        if any(LEVEL_RANK[f.level] >= LEVEL_RANK[level] for f in recent):
            continue
        flag = RiskFlag.objects.create(client=client, level=level, source_type=RiskFlag.SourceType.CHAT,
                                       message=message, reason=CHAT_FLAG_REASONS[level])
        notify_therapists(flag)
    return notified


def notify_therapists(flag: RiskFlag) -> None:
    """Email the client's active therapists that a flag needs review. No clinical content in the email."""
    recipients = list(
        CareRelationship.objects.filter(client=flag.client, status=CareRelationship.Status.ACTIVE)
        .exclude(therapist__email="").values_list("therapist__email", flat=True)
    )
    if not recipients:
        return
    try:
        send_mail(
            subject="A safety flag needs your review" + (" (urgent)" if flag.level == "imminent" else ""),
            message=(
                "A safety flag was raised for one of your clients on TherapyBot.\n\n"
                f"Review it here: {settings.FRONTEND_URL}/practice\n\n"
                "TherapyBot shows the client crisis resources when this happens. Clients are told flags are not "
                "monitored in real time."
            ),
            from_email=None,
            recipient_list=recipients,
        )
    except Exception:
        logger.exception("Failed to send risk flag notification for flag %s", flag.pk)


# --- Conversation summaries the client shares ---------------------------------------------------------


def care_summary(conversation: Conversation) -> str:
    """The therapist-facing summary, regenerated only when the conversation has new messages."""
    count = conversation.messages.count()
    if conversation.care_summary and conversation.care_summary_count == count:
        return conversation.care_summary
    recent = list(conversation.messages.order_by("-created_at", "-id")[:SUMMARY_MESSAGES])
    transcript = "\n".join(
        f"{'Client' if m.role == Message.Role.USER else 'Companion'}: {m.content}" for m in reversed(recent)
    )
    earlier = f"Earlier in the conversation (summary):\n{conversation.summary}\n\n" if conversation.summary else ""
    text = llm.get_chat_model().complete([
        llm.system(CARE_SUMMARY_PROMPT), llm.user(f"{earlier}Conversation:\n{transcript}\n\nSummary:"),
    ]).strip()[:1500]
    conversation.care_summary, conversation.care_summary_count = text, count
    conversation.save(update_fields=["care_summary", "care_summary_count"])
    return text


FLAGGED_NOTE = "The companion's safety check flagged risk in this conversation."


def was_flagged(conversation: Conversation) -> bool:
    """From the stored screening result, not the summary: the model's wording can't hide a flag."""
    return conversation.messages.filter(role=Message.Role.USER).exclude(risk_level=Message.Risk.NONE).exists()


def window_start(client: Client):
    """'Between sessions' means since the last completed session, or the last two weeks if none."""
    last = (
        Session.objects.filter(client=client, status=Session.Status.COMPLETED, date__lte=timezone.localdate())
        .order_by("-date").first()
    )
    return last.date if last else timezone.localdate() - timedelta(days=DEFAULT_WINDOW_DAYS)


def shared_conversations(client: Client, relationship: CareRelationship, since):
    if client.user_id is None or not (relationship.share_chat_summaries or relationship.share_raw_chat):
        return Conversation.objects.none()
    return Conversation.objects.filter(
        user_id=client.user_id, shared_with_care_team=True, updated_at__date__gte=since, messages__isnull=False
    ).distinct().order_by("-updated_at")[:MAX_SHARED_CONVERSATIONS]


def between_sessions(client: Client, relationship: CareRelationship) -> dict:
    """What happened in the companion since the last session, limited to what the client shares."""
    since = window_start(client)
    conversations = []
    for conversation in shared_conversations(client, relationship, since):
        item = {"id": conversation.pk, "title": conversation.title, "updated_at": conversation.updated_at,
                "message_count": conversation.messages.count(), "flagged": was_flagged(conversation),
                "summary": None, "messages": None}
        if relationship.share_chat_summaries:
            try:
                item["summary"] = care_summary(conversation)
            except Exception:
                logger.warning("Care summary failed for conversation %s", conversation.pk, exc_info=True)
        if relationship.share_raw_chat:
            item["messages"] = [
                {"role": m.role, "content": m.content, "created_at": m.created_at}
                for m in conversation.messages.order_by("created_at", "id")
            ]
        conversations.append(item)
    chat_flags = RiskFlag.objects.filter(
        client=client, source_type=RiskFlag.SourceType.CHAT, created_at__date__gte=since
    ).count()
    return {
        "since": since.isoformat(),
        "sharing": {scope: getattr(relationship, scope)
                    for scope in ("share_checkins", "share_chat_summaries", "share_raw_chat")},
        "conversations": conversations,
        "chat_flags": chat_flags,
    }


def summary_chunks(client: Client, relationship: CareRelationship | None, limit: int = 3) -> list[RetrievedChunk]:
    """Shared conversation summaries as citable sources for session prep."""
    if relationship is None or not relationship.share_chat_summaries:
        return []
    chunks = []
    for conversation in shared_conversations(client, relationship, window_start(client))[:limit]:
        try:
            text = care_summary(conversation)
        except Exception:
            logger.warning("Care summary failed for conversation %s", conversation.pk, exc_info=True)
            continue
        if text and was_flagged(conversation):
            text = f"{FLAGGED_NOTE} {text}"
        if text:
            chunks.append(RetrievedChunk(
                chunk_id=-conversation.pk, text=text, score=0.0, document_id=None, session_id=None,
                session_date=conversation.updated_at.date().isoformat(), doc_type="chat_summary",
            ))
    return chunks
