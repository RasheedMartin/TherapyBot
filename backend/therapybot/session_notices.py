"""
Telling clients about their sessions: an email when one is scheduled, moved or cancelled, with a calendar
file attached. The subject stays neutral ("Your appointment on ...") because subjects show on lock screens.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from therapybot.calendar_feed import render_calendar
from therapybot.models import CareRelationship, Session

logger = logging.getLogger(__name__)


def _when(session: Session) -> str:
    day = f"{session.date:%A, %B} {session.date.day}"
    if not session.start_time:
        return day
    hour = session.start_time.strftime("%I:%M %p").lstrip("0")
    return f"{day} at {hour}"


def notify_client(session: Session, kind: str, series: int = 1) -> bool:
    """kind is "scheduled", "rescheduled" or "cancelled". Returns True if an email was sent."""
    from therapybot.serializers import therapist_display_name

    client = session.client
    user = client.user
    active = CareRelationship.objects.filter(
        client=client, therapist=session.therapist, status=CareRelationship.Status.ACTIVE
    ).exists()
    if user is None or not user.email or not active:
        return False

    therapist = therapist_display_name(session.therapist)
    when = _when(session)
    if kind == "cancelled":
        lead = f"{therapist} cancelled your session on {when}."
    elif kind == "rescheduled":
        lead = f"{therapist} moved your session to {when} ({session.duration_minutes} minutes)."
    else:
        repeat = f" It repeats weekly for {series} sessions." if series > 1 else ""
        lead = f"{therapist} scheduled a session with you on {when} ({session.duration_minutes} minutes).{repeat}"
    sessions = [session]
    if series > 1:
        sessions = list(
            Session.objects.filter(client=client, therapist=session.therapist, date__gte=session.date,
                                   start_time=session.start_time, status=Session.Status.SCHEDULED)
            .order_by("date")[:series]
        )
    title = f"Therapy session · {therapist}"
    ics = render_calendar("TherapyBot sessions", [], sessions=[(s, title) for s in sessions])
    message = EmailMessage(
        subject=f"Your appointment on {session.date:%a, %b} {session.date.day}" + (" is cancelled" if kind == "cancelled" else ""),
        body=(
            f"Hi {user.first_name or user.username},\n\n{lead}\n\n"
            + ("" if kind == "cancelled" else "The attached file adds it to your calendar. ")
            + f"You can see your upcoming sessions any time at {settings.FRONTEND_URL}\n\n"
            "If you need to change it, contact your therapist."
        ),
        to=[user.email],
    )
    message.attach("session.ics", ics, "text/calendar")
    try:
        message.send()
    except Exception:
        logger.exception("Failed to send %s notice for session %s", kind, session.pk)
        return False
    return True
