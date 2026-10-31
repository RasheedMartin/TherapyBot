"""
Facts about a client computed from the database, not the model: dates, counts, homework completion.
These go to the UI as-is and to the model as givens it may restate but never change.
"""

from datetime import timedelta

from django.utils import timezone

from therapybot.models import CareRelationship, Client, ClinicalDocument, Plan, Session

HOMEWORK_WINDOW_DAYS = 14


def _homework(client: Client, shares_checkins: bool) -> list[dict]:
    today = timezone.localdate()
    since = today - timedelta(days=HOMEWORK_WINDOW_DAYS - 1)
    items = []
    for plan in Plan.objects.filter(client=client, archived=False).prefetch_related("steps__check_ins"):
        for step in plan.steps.all():
            item = {"plan": plan.title, "step": step.title, "frequency": step.frequency}
            if shares_checkins:
                days = [since + timedelta(days=i) for i in range(HOMEWORK_WINDOW_DAYS)]
                due = [d for d in days if step.is_due_on(d)]
                done = {c.date for c in step.check_ins.all()}
                item["done_last_14_days"] = sum(d in done for d in due)
                item["due_last_14_days"] = len(due)
            items.append(item)
    return items


def client_facts(client: Client, therapist) -> dict:
    sessions = Session.objects.filter(client=client).exclude(status=Session.Status.CANCELLED)
    completed = sessions.filter(status=Session.Status.COMPLETED, date__lte=timezone.localdate())
    last = completed.first()
    upcoming = sessions.filter(status=Session.Status.SCHEDULED, date__gte=timezone.localdate()).order_by("date").first()
    relationship = CareRelationship.objects.filter(
        client=client, therapist=therapist, status=CareRelationship.Status.ACTIVE
    ).first()
    shares_checkins = bool(relationship and relationship.share_checkins)
    return {
        "sessions_completed": completed.count(),
        "last_session_date": last.date.isoformat() if last else None,
        "last_session_modality": last.get_modality_display() if last else None,
        "next_session_date": upcoming.date.isoformat() if upcoming else None,
        "draft_notes": ClinicalDocument.objects.filter(client=client, status=ClinicalDocument.Status.DRAFT).count(),
        "client_shares_checkins": shares_checkins,
        "homework": _homework(client, shares_checkins),
    }


def render_facts(facts: dict) -> str:
    """The FACTS block given to the model."""
    lines = [
        f"Completed sessions: {facts['sessions_completed']}",
        f"Last session: {facts['last_session_date'] or 'none recorded'}"
        + (f" ({facts['last_session_modality']})" if facts["last_session_modality"] else ""),
        f"Next session: {facts['next_session_date'] or 'not scheduled'}",
    ]
    if not facts["homework"]:
        lines.append("Assigned homework: none")
    for hw in facts["homework"]:
        if "done_last_14_days" in hw:
            progress = f"done {hw['done_last_14_days']} of {hw['due_last_14_days']} times due in the last 14 days"
        else:
            progress = "completion not shared by the client"
        lines.append(f"Homework: {hw['step']} ({hw['frequency']}) – {progress}")
    return "\n".join(lines)
