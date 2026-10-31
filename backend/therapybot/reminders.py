"""
Daily reminder emails: the day's plan steps, each with a one-tap "done" link.

Links carry signed tokens instead of requiring sign-in. They open a confirmation page in the
app rather than checking in directly, because email security scanners pre-fetch links.
"""

import datetime
import logging
from html import escape

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives

from therapybot.models import PlanStep, Profile

logger = logging.getLogger(__name__)

CHECK_IN_SALT = "therapybot.reminders.check-in"
UNSUBSCRIBE_SALT = "therapybot.reminders.unsubscribe"
CHECK_IN_MAX_AGE = 60 * 60 * 24 * 7
SEND_WINDOW = datetime.timedelta(hours=3)  # don't send a morning reminder at midnight if the job was down


def check_in_token(step: PlanStep, day: datetime.date) -> str:
    return signing.dumps({"s": step.pk, "d": day.isoformat()}, salt=CHECK_IN_SALT, compress=True)


def read_check_in_token(token: str) -> tuple[int, datetime.date]:
    data = signing.loads(token, salt=CHECK_IN_SALT, max_age=CHECK_IN_MAX_AGE)
    return data["s"], datetime.date.fromisoformat(data["d"])


def unsubscribe_token(user) -> str:
    return signing.dumps(user.pk, salt=UNSUBSCRIBE_SALT)


def read_unsubscribe_token(token: str) -> int:
    return signing.loads(token, salt=UNSUBSCRIBE_SALT)


def due_steps(user, day: datetime.date) -> list[PlanStep]:
    """Steps due on `day` across the user's active plans that aren't done yet, earliest time first."""
    steps = (
        PlanStep.objects.filter(plan__user=user, plan__archived=False)
        .select_related("plan")
        .prefetch_related("check_ins")
    )
    pending = [s for s in steps if s.is_due_on(day) and day not in {c.date for c in s.check_ins.all()}]
    return sorted(pending, key=lambda s: (s.time_of_day is None, s.time_of_day or datetime.time(), s.order))


def _format_time(t: datetime.time | None) -> str:
    return t.strftime("%I:%M %p").lstrip("0") if t else ""


def send_reminder(profile: Profile, day: datetime.date, steps: list[PlanStep]) -> None:
    user = profile.user
    name = profile.display_name or user.username
    app = settings.FRONTEND_URL
    unsubscribe_page = f"{app}/reminders/off?t={unsubscribe_token(user)}"
    one_click = f"{settings.API_BASE_URL}/api/reminders/unsubscribe/?t={unsubscribe_token(user)}"

    text_lines = [f"Hi {name},", "", "Here's what's on your plan today:", ""]
    html_items = []
    for step in steps:
        link = f"{app}/check-in?t={check_in_token(step, day)}"
        when = f" ({_format_time(step.time_of_day)})" if step.time_of_day else ""
        text_lines += [f"- {step.title}{when}", f"  Mark done: {link}"]
        html_items.append(
            f'<li style="margin:0 0 14px"><strong>{escape(step.title)}</strong>'
            f'<span style="color:#5b6764">{escape(when)}</span><br>'
            f'<a href="{escape(link)}" style="color:#2f6f62;font-weight:600">Mark done ✓</a></li>'
        )
    text_lines += [
        "",
        "Small steps count. Do what feels doable today.",
        "",
        f"Open TherapyBot: {app}/",
        f"Stop these emails: {unsubscribe_page}",
        "",
        "In crisis? Call or text 988 (US).",
    ]
    html = f"""<div style="font-family:system-ui,-apple-system,sans-serif;max-width:520px;color:#1f2a27;line-height:1.5">
<p>Hi {escape(name)},</p>
<p>Here's what's on your plan today:</p>
<ul style="padding-left:20px">{''.join(html_items)}</ul>
<p>Small steps count. Do what feels doable today.</p>
<p><a href="{escape(app)}/" style="color:#2f6f62">Open TherapyBot</a></p>
<p style="font-size:12px;color:#5b6764">In crisis? Call or text 988 (US).<br>
<a href="{escape(unsubscribe_page)}" style="color:#5b6764">Stop daily reminders</a></p></div>"""

    message = EmailMultiAlternatives(
        subject=f"Today's plan: {len(steps)} small step{'s' if len(steps) != 1 else ''}",
        body="\n".join(text_lines),
        to=[user.email],
        headers={"List-Unsubscribe": f"<{one_click}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
    )
    message.attach_alternative(html, "text/html")
    message.send()


def send_due_reminders(now: datetime.datetime | None = None) -> int:
    """Send each user's reminder once per local day, at or shortly after their chosen time."""
    sent = 0
    profiles = Profile.objects.filter(
        reminders_enabled=True, email_verified_at__isnull=False, user__is_active=True
    ).select_related("user")
    for profile in profiles:
        local = profile.local_now() if now is None else now.astimezone(profile.local_now().tzinfo)
        today = local.date()
        if profile.reminder_last_sent == today:
            continue
        scheduled = datetime.datetime.combine(today, profile.reminder_time, tzinfo=local.tzinfo)
        if not scheduled <= local < scheduled + SEND_WINDOW:
            continue
        steps = due_steps(profile.user, today)
        if steps:
            try:
                send_reminder(profile, today, steps)
                sent += 1
            except Exception:
                logger.exception("Failed to send reminder to user %s", profile.user_id)
                continue
        profile.reminder_last_sent = today
        profile.save(update_fields=["reminder_last_sent"])
    return sent
