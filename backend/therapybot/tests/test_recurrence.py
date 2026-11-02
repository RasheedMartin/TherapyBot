"""Repeating sessions: weekly, every 2 weeks, chosen days, monthly on the same weekday; and how series end."""

from datetime import date, timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from therapybot.clinical.recurrence import RecurrenceError, Repeat, occurrences
from therapybot.models import Session
from therapybot.tests.helpers import APITestCase

TUE = date(2026, 1, 6)  # the first Tuesday of January 2026


def series(start, **rule):
    return occurrences(start, Repeat.parse(rule, start))


class OccurrenceTests(SimpleTestCase):
    def test_weekly_and_every_two_weeks(self):
        self.assertEqual(series(TUE, frequency="weekly", count=3), [TUE, date(2026, 1, 13), date(2026, 1, 20)])
        self.assertEqual(series(TUE, frequency="biweekly", until="2026-02-03"),
                         [TUE, date(2026, 1, 20), date(2026, 2, 3)])

    def test_chosen_days_each_week_always_include_the_first_sessions_day(self):
        dates = series(TUE, frequency="days", weekdays=[4], count=4)  # Friday picked; Tuesday implied
        self.assertEqual(dates, [TUE, date(2026, 1, 9), date(2026, 1, 13), date(2026, 1, 16)])

    def test_monthly_keeps_the_same_weekday_and_a_fifth_weekday_becomes_last(self):
        self.assertEqual(series(TUE, frequency="monthly", count=3), [TUE, date(2026, 2, 3), date(2026, 3, 3)])
        fifth_thursday = date(2026, 1, 29)  # there is no 5th Thursday in February 2026: use the last one
        self.assertEqual(series(fifth_thursday, frequency="monthly", count=2)[1], date(2026, 2, 26))
        self.assertIn("first Tuesday", Repeat.parse({"frequency": "monthly", "count": 2}, TUE).describe(TUE))

    def test_every_series_ends_and_is_bounded(self):
        for bad in ({"frequency": "weekly"}, {"frequency": "weekly", "count": 1},
                    {"frequency": "weekly", "count": 80}, {"frequency": "weekly", "until": "2025-12-01"},
                    {"frequency": "weekly", "until": "2027-06-01"}, {"frequency": "days", "weekdays": [1], "count": 3},
                    {"frequency": "hourly", "count": 3}):
            with self.assertRaises(RecurrenceError, msg=bad):
                Repeat.parse(bad, TUE)
        self.assertIsNone(Repeat.parse({"frequency": "none"}, TUE))


class SeriesApiTests(APITestCase):
    def test_booking_a_series_shares_one_id_and_reports_the_end(self):
        therapist = self.make_therapist()
        client_record, _ = self.link(therapist, self.make_user())
        self.login(therapist)
        start = timezone.localdate() + timedelta(days=1)
        res = self.client.post(f"/api/practice/clients/{client_record.pk}/sessions/", {
            "date": start.isoformat(), "start_time": "09:00", "status": "scheduled",
            "repeat": {"frequency": "biweekly", "count": 4},
        }, format="json")
        self.assertEqual((res.status_code, res.data["created"]), (201, 4))
        self.assertEqual(res.data["last_date"], start + timedelta(weeks=6))
        ids = set(Session.objects.filter(client=client_record).values_list("series_id", flat=True))
        self.assertEqual(len(ids), 1)
        self.assertIsNotNone(ids.pop())
        bad = self.client.post(f"/api/practice/clients/{client_record.pk}/sessions/", {
            "date": start.isoformat(), "repeat": {"frequency": "weekly"}}, format="json")
        self.assertIn("ends", bad.data["repeat"][0])
