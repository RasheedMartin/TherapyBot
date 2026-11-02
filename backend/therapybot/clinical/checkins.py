"""
Check-ins a therapist sends: a screening the client completes from their portal, once or on a repeat.
The client gets a short email when one is due; the subject stays neutral because it shows on lock screens.
"""

import calendar
import logging
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import F
from django.utils import timezone

from therapybot.models import CareRelationship, ScreeningAssignment

logger = logging.getLogger(__name__)

Repeat = ScreeningAssignment.Repeat


def _add_month(day: date) -> date:
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def step(day: date, repeat: str) -> date:
    if repeat == Repeat.MONTHLY:
        return _add_month(day)
    return day + timedelta(days=14 if repeat == Repeat.BIWEEKLY else 7)


def visible(queryset):
    """Assignments the client can act on: still active, from a therapist currently in their care."""
    return queryset.filter(
        active=True,
        client__relationships__therapist=F("assigned_by"),
        client__relationships__status=CareRelationship.Status.ACTIVE,
    ).distinct()


def complete(assignment: ScreeningAssignment, today: date | None = None) -> None:
    """Mark this round done. A repeat moves to its next date after today; missed rounds aren't stacked up."""
    today = today or timezone.localdate()
    assignment.last_completed_on = today
    if assignment.repeat == Repeat.ONCE:
        assignment.active = False
    else:
        while assignment.due_on <= today:
            assignment.due_on = step(assignment.due_on, assignment.repeat)
    assignment.save(update_fields=["last_completed_on", "active", "due_on"])


def notify(assignment: ScreeningAssignment) -> bool:
    """
    Email the client that a check-in is ready, once per due date. Returns True if sent. The email leaves out
    the check-in's name and the therapist's note: inboxes aren't private, so those stay in the app.
    """
    from therapybot.serializers import therapist_display_name

    user = assignment.client.user
    if user is None or not user.email or assignment.notified_for == assignment.due_on:
        return False
    therapist = therapist_display_name(assignment.assigned_by)
    message = EmailMessage(
        subject="You have a new check-in",
        body=(
            f"Hi {user.first_name or user.username},\n\n{therapist} sent you a short check-in. It takes a few "
            "minutes and helps them see how things are going between sessions.\n\n"
            f"Sign in to complete it: {settings.FRONTEND_URL}"
        ),
        to=[user.email],
    )
    try:
        message.send()
    except Exception:  # noqa: BLE001 - an email failure must not undo the assignment
        logger.exception("Check-in email failed")
        return False
    assignment.notified_for = assignment.due_on
    assignment.save(update_fields=["notified_for"])
    return True


def send_due_notices(today: date | None = None) -> int:
    """Email clients whose repeating check-ins came due since they were last told. For the daily job."""
    today = today or timezone.localdate()
    sent = 0
    due = visible(ScreeningAssignment.objects.filter(due_on__lte=today)).exclude(notified_for=F("due_on"))
    for assignment in due.select_related("client__user", "assigned_by__profile"):
        sent += notify(assignment)
    return sent
