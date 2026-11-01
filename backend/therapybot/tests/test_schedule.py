"""Scheduling sessions, the therapist's schedule, and sessions in calendar feeds."""

from datetime import time, timedelta

from django.utils import timezone

from therapybot.models import Profile, Session
from therapybot.tests.helpers import APITestCase


class SchedulingTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.client_record, self.rel = self.link(self.therapist, self.make_user())
        self.monday = timezone.localdate() + timedelta(days=7 - timezone.localdate().weekday())
        self.login(self.therapist)

    def test_weekly_series_and_validation(self):
        url = f"/api/practice/clients/{self.client_record.pk}/sessions/"
        res = self.client.post(url, {"date": self.monday.isoformat(), "start_time": "14:00", "duration_minutes": 50,
                                     "modality": "cbt", "status": "scheduled", "repeat_weeks": 3}, format="json")
        self.assertEqual((res.status_code, res.data["created"]), (201, 4))
        sessions = Session.objects.filter(client=self.client_record).order_by("date")
        self.assertEqual([s.date for s in sessions], [self.monday + timedelta(weeks=w) for w in range(4)])
        self.assertTrue(all(s.start_time == time(14, 0) and s.status == "scheduled" for s in sessions))

        bad = self.client.post(url, {"date": self.monday.isoformat(), "repeat_weeks": 40}, format="json")
        self.assertEqual(bad.status_code, 400)
        short = self.client.post(url, {"date": self.monday.isoformat(), "duration_minutes": 5}, format="json")
        self.assertIn("duration_minutes", short.data)

    def test_reschedule_and_cancel_only_by_their_therapist(self):
        session = Session.objects.create(client=self.client_record, therapist=self.therapist, date=self.monday,
                                         status="scheduled")
        url = f"/api/practice/clients/{self.client_record.pk}/sessions/{session.pk}/"
        res = self.client.patch(url, {"start_time": "09:30", "status": "cancelled"}, format="json")
        self.assertEqual((res.data["start_time"], res.data["status"]), ("09:30:00", "cancelled"))
        self.login(self.make_therapist("drkim", "drkim@example.com"))
        self.assertEqual(self.client.patch(url, {"status": "completed"}, format="json").status_code, 404)

    def test_schedule_shows_only_this_therapists_active_clients_in_range(self):
        mine = Session.objects.create(client=self.client_record, therapist=self.therapist, date=self.monday,
                                      start_time=time(15, 0), status="scheduled")
        Session.objects.create(client=self.client_record, therapist=self.therapist,
                               date=self.monday + timedelta(days=10), status="scheduled")  # next week
        ended_client, ended_rel = self.link(self.therapist, self.make_user("bob", "bob@example.com"))
        Session.objects.create(client=ended_client, therapist=self.therapist, date=self.monday, status="scheduled")
        ended_rel.status = "ended"
        ended_rel.save()
        other = self.make_therapist("drkim", "drkim@example.com")
        other_client, _ = self.link(other, self.make_user("cara", "cara@example.com"))
        Session.objects.create(client=other_client, therapist=other, date=self.monday, status="scheduled")

        res = self.client.get(f"/api/practice/schedule/?start={self.monday}")
        self.assertEqual([s["id"] for s in res.data["sessions"]], [mine.pk])
        self.assertEqual(res.data["sessions"][0]["client_name"], self.client_record.display_name)
        far = (self.monday + timedelta(days=100)).isoformat()
        self.assertEqual(self.client.get(f"/api/practice/schedule/?start={self.monday}&end={far}").status_code, 400)


class SessionCalendarFeedTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.user = self.make_user()
        self.client_record, self.rel = self.link(self.therapist, self.user)
        self.client_record.display_name = "Jordan Ellis"
        self.client_record.save()
        day = timezone.localdate() + timedelta(days=2)
        Session.objects.create(client=self.client_record, therapist=self.therapist, date=day,
                               start_time=time(14, 0), duration_minutes=50, status="scheduled")
        Session.objects.create(client=self.client_record, therapist=self.therapist, date=day + timedelta(days=7),
                               start_time=time(14, 0), status="cancelled")

    def feed(self, user, discreet=False):
        Profile.objects.filter(user=user).update(calendar_token=f"tok-{user.pk}", calendar_discreet=discreet)
        return self.client.get(f"/api/calendar/tok-{user.pk}.ics").content.decode()

    def test_therapist_feed_uses_initials_never_full_names(self):
        body = self.feed(self.therapist)
        self.assertIn("SUMMARY:Session · J.E.", body)
        self.assertNotIn("Jordan", body)
        self.assertIn("DURATION:PT50M", body)
        self.assertIn("STATUS:CANCELLED", body)
        self.assertIn("X-WR-CALNAME:TherapyBot sessions", body)

    def test_client_feed_names_their_therapist_and_respects_discreet_and_consent(self):
        body = self.feed(self.user)
        self.assertIn("Therapy session · Dana Lee", body)
        self.assertNotIn("Dana", self.feed(self.user, discreet=True))
        self.assertIn("SUMMARY:Appointment", self.feed(self.user, discreet=True))
        self.rel.status = "ended"
        self.rel.save()
        self.assertNotIn("therapybot-session-", self.feed(self.user))
