"""iCalendar (.ics) rendering for plans and therapy sessions, used by the one-off download and the subscription feed."""

from datetime import date, datetime, timedelta

from django.utils import timezone

from therapybot.models import PlanStep, Session

ICS_DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
DISCREET_TITLE = "Personal check-in"
DISCREET_SESSION_TITLE = "Appointment"
RRULES = {
    PlanStep.Frequency.DAILY: "FREQ=DAILY",
    PlanStep.Frequency.WEEKDAYS: "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """RFC 5545 caps lines at 75 octets; continuation lines start with a space."""
    out, current = [], ""
    for char in line:
        if len((current + char).encode()) > 74:
            out.append(current)
            current = " " + char
        else:
            current += char
    return out + [current]


def _first_occurrence(step: PlanStep, anchor: date) -> date:
    if step.frequency == PlanStep.Frequency.WEEKLY and step.weekday is not None:
        return anchor + timedelta(days=(step.weekday - anchor.weekday()) % 7)
    if step.frequency == PlanStep.Frequency.WEEKDAYS:
        while anchor.weekday() > 4:
            anchor += timedelta(days=1)
    return anchor


def _event(step: PlanStep, stamp: str, today: date, discreet: bool) -> list[str]:
    if step.frequency == PlanStep.Frequency.ONCE:
        # An unfinished one-off step floats to today; a finished one stays on the day it was done
        done = max((c.date for c in step.check_ins.all()), default=None)
        start = done or today
    else:
        # Anchor recurring steps to when the plan began so the series is stable between feed refreshes
        start = _first_occurrence(step, timezone.localtime(step.plan.created_at).date())

    title = DISCREET_TITLE if discreet else step.title
    lines = [
        "BEGIN:VEVENT",
        f"UID:therapybot-step-{step.pk}@therapybot.app",
        f"DTSTAMP:{stamp}",
        f"SUMMARY:{_escape(title)}",
    ]
    if step.details and not discreet:
        lines.append(f"DESCRIPTION:{_escape(step.details)}")
    if step.time_of_day:
        lines += [f"DTSTART:{start:%Y%m%d}T{step.time_of_day:%H%M}00", "DURATION:PT15M"]
    else:
        lines += [f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{start + timedelta(days=1):%Y%m%d}"]

    rrule = RRULES.get(step.frequency)
    if step.frequency == PlanStep.Frequency.WEEKLY:
        rrule = f"FREQ=WEEKLY;BYDAY={ICS_DAYS[step.weekday or 0]}"
    if rrule:
        lines.append(f"RRULE:{rrule}")
    if step.time_of_day:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_escape(title)}", "TRIGGER:-PT10M", "END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def _session_event(session: Session, title: str, stamp: str) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:therapybot-session-{session.pk}@therapybot.app",
        f"DTSTAMP:{stamp}",
        f"SUMMARY:{_escape(title)}",
    ]
    if session.start_time:
        start = datetime.combine(session.date, session.start_time)
        lines += [f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DURATION:PT{session.duration_minutes}M"]
    else:
        lines += [f"DTSTART;VALUE=DATE:{session.date:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{session.date + timedelta(days=1):%Y%m%d}"]
    if session.status == Session.Status.CANCELLED:
        lines.append("STATUS:CANCELLED")  # calendars that already have it remove or strike it
    elif session.status == Session.Status.SCHEDULED and session.start_time:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_escape(title)}", "TRIGGER:-PT30M", "END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def render_calendar(name: str, steps, discreet: bool = False, sessions=()) -> str:
    """
    `sessions` is a list of (Session, title) pairs; the caller chooses titles, since what's appropriate
    differs for therapist and client calendars.
    """
    """Times are 'floating' (no time zone), so they follow whatever time zone the user's calendar is in."""
    stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    today = timezone.localdate()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TherapyBot//Plans//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    for step in steps:
        lines += _event(step, stamp, today, discreet)
    for session, title in sessions:
        lines += _session_event(session, DISCREET_SESSION_TITLE if discreet else title, stamp)
    lines.append("END:VCALENDAR")
    return "\r\n".join(folded for line in lines for folded in _fold(line)) + "\r\n"
