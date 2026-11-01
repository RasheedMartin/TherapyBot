"""
Repeating sessions the way a practice books them: weekly, every two weeks, on chosen days each week
(e.g. Monday and Thursday), or monthly on the same weekday ("the first Tuesday"). Sessions are created up
front, so every series ends: after a number of sessions or on a date, and never more than a year out.
"""

from dataclasses import dataclass
from datetime import date, timedelta

MAX_SESSIONS = 52
MAX_SPAN_DAYS = 366
FREQUENCIES = ("weekly", "biweekly", "days", "monthly")
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ORDINALS = ["first", "second", "third", "fourth", "last"]


class RecurrenceError(ValueError):
    """A repeat rule the therapist needs to fix; the message is shown to them."""


@dataclass(frozen=True)
class Repeat:
    frequency: str
    weekdays: tuple[int, ...] = ()  # for "days": 0 = Monday
    count: int | None = None  # total sessions including the first
    until: date | None = None

    @classmethod
    def parse(cls, data, start: date) -> "Repeat | None":
        """From the API payload; None means a single session."""
        if not data or data.get("frequency") in (None, "", "none"):
            return None
        frequency = data.get("frequency")
        if frequency not in FREQUENCIES:
            raise RecurrenceError("Choose how often the session repeats.")
        weekdays = tuple(sorted({int(d) for d in data.get("weekdays") or [] if str(d).isdigit() and 0 <= int(d) <= 6}))
        if frequency == "days":
            weekdays = tuple(sorted(set(weekdays) | {start.weekday()}))  # the first session's day is always one
            if len(weekdays) < 2:
                raise RecurrenceError("Pick at least two days of the week, or choose weekly.")
        count, until = data.get("count"), data.get("until")
        if count in (None, "") and not until:
            raise RecurrenceError("Choose when the series ends: after a number of sessions or on a date.")
        if count not in (None, ""):
            try:
                count = int(count)
            except (TypeError, ValueError):
                raise RecurrenceError("The number of sessions must be a whole number.")
            if not 2 <= count <= MAX_SESSIONS:
                raise RecurrenceError(f"A series has 2 to {MAX_SESSIONS} sessions.")
        else:
            count = None
        if until:
            try:
                until = date.fromisoformat(str(until))
            except ValueError:
                raise RecurrenceError("Enter a valid end date.")
            if until <= start:
                raise RecurrenceError("The end date must be after the first session.")
            if (until - start).days > MAX_SPAN_DAYS:
                raise RecurrenceError("A series can run for up to a year.")
        else:
            until = None
        return cls(frequency=frequency, weekdays=weekdays, count=count, until=until)

    def describe(self, start: date) -> str:
        """Plain words for emails and confirmations, e.g. "every 2 weeks"."""
        if self.frequency == "weekly":
            return f"every week on {WEEKDAY_NAMES[start.weekday()]}"
        if self.frequency == "biweekly":
            return f"every 2 weeks on {WEEKDAY_NAMES[start.weekday()]}"
        if self.frequency == "days":
            names = [WEEKDAY_NAMES[d] for d in self.weekdays]
            return "every week on " + (", ".join(names[:-1]) + " and " + names[-1])
        return f"monthly on the {ORDINALS[_nth(start) - 1]} {WEEKDAY_NAMES[start.weekday()]}"


def _nth(day: date) -> int:
    """Which occurrence of its weekday this is in the month (1-4), or 5 for the last one."""
    return min((day.day - 1) // 7 + 1, 5)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth weekday of a month; n = 5 means the last one."""
    first = date(year, month, 1)
    day = first + timedelta(days=(weekday - first.weekday()) % 7)
    if n == 5:
        while (day + timedelta(days=7)).month == month:
            day += timedelta(days=7)
        return day
    return day + timedelta(weeks=n - 1)


def occurrences(start: date, repeat: Repeat) -> list[date]:
    """Every date in the series, starting with `start`."""
    limit = start + timedelta(days=MAX_SPAN_DAYS)
    end = min(repeat.until or limit, limit)
    count = repeat.count or MAX_SESSIONS
    dates = [start]

    if repeat.frequency in ("weekly", "biweekly"):
        step = timedelta(weeks=1 if repeat.frequency == "weekly" else 2)
        day = start + step
        while len(dates) < count and day <= end:
            dates.append(day)
            day += step
    elif repeat.frequency == "days":
        day = start + timedelta(days=1)
        while len(dates) < count and day <= end:
            if day.weekday() in repeat.weekdays:
                dates.append(day)
            day += timedelta(days=1)
    else:  # monthly on the same weekday ("second Tuesday"); a 5th weekday becomes "last"
        n = _nth(start)
        year, month = start.year, start.month
        while len(dates) < count:
            month += 1
            if month > 12:
                year, month = year + 1, 1
            day = _nth_weekday(year, month, start.weekday(), n)
            if day > end:
                break
            dates.append(day)
    return dates
