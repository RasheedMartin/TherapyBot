"""Scheduling sessions, the therapist's schedule, and sessions in calendar feeds."""

from datetime import time, timedelta

from django.utils import timezone

from therapybot.models import CareRelationship, Profile, Session
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


class OverviewTests(APITestCase):
    def test_what_needs_attention_across_clients_in_care(self):
        from therapybot.models import ClinicalDocument, RiskFlag

        therapist = self.make_therapist()
        today = timezone.localdate()
        jordan, _ = self.link(therapist, self.make_user("jordan", "jordan@example.com"))
        priya, _ = self.link(therapist, self.make_user("priya", "priya@example.com"))
        ended, ended_rel = self.link(therapist, self.make_user("bob", "bob@example.com"))
        ended_rel.status = "ended"
        ended_rel.save()

        todays = Session.objects.create(client=jordan, therapist=therapist, date=today, start_time=time(9, 0),
                                        status="scheduled")
        stale = Session.objects.create(client=jordan, therapist=therapist, date=today - timedelta(days=3),
                                       status="scheduled")  # never closed out
        undocumented = Session.objects.create(client=priya, therapist=therapist, date=today - timedelta(days=2))
        documented = Session.objects.create(client=priya, therapist=therapist, date=today - timedelta(days=9))
        ClinicalDocument.objects.create(client=priya, session=documented, doc_type="progress_note", status="final",
                                        title="Note", text="Seen and documented.")
        draft = ClinicalDocument.objects.create(client=jordan, author=therapist, doc_type="progress_note",
                                                status="draft", title="Draft", text="To sign.")
        Session.objects.create(client=ended, therapist=therapist, date=today, status="scheduled")  # not in care
        RiskFlag.objects.create(client=priya, level="elevated", source_type="screening", reason="PHQ-9 item 9")

        self.login(therapist)
        data = self.client.get("/api/practice/overview/").data
        self.assertEqual([s["id"] for s in data["today"]], [todays.pk])
        self.assertEqual([s["id"] for s in data["to_close"]], [stale.pk])
        self.assertEqual([s["id"] for s in data["needs_note"]], [undocumented.pk])
        self.assertEqual([d["id"] for d in data["drafts"]], [draft.pk])
        self.assertEqual([c["display_name"] for c in data["unscheduled"]], [priya.display_name])
        self.assertEqual((data["open_flags"], data["active_clients"]), (1, 2))

        self.login(self.make_user("carl", "carl@example.com"))
        self.assertEqual(self.client.get("/api/practice/overview/").status_code, 403)


class DraftDeletionTests(APITestCase):
    def test_only_the_author_deletes_drafts_and_signed_notes_stay(self):
        from therapybot.models import AuditEvent, ClinicalDocument

        therapist = self.make_therapist()
        client_record, _ = self.link(therapist, self.make_user())
        colleague = self.make_therapist("drkim", "drkim@example.com")
        CareRelationship.objects.create(client=client_record, therapist=colleague, status="active")
        draft = ClinicalDocument.objects.create(client=client_record, author=therapist, doc_type="progress_note",
                                                status="draft", title="Draft", text="Work in progress.")
        signed = ClinicalDocument.objects.create(client=client_record, author=therapist, doc_type="progress_note",
                                                 status="final", title="Signed", text="Final.")
        url = lambda d: f"/api/practice/clients/{client_record.pk}/documents/{d.pk}/"

        self.login(colleague)
        self.assertEqual(self.client.delete(url(draft)).status_code, 403)
        self.login(therapist)
        self.assertEqual(self.client.delete(url(signed)).status_code, 409)
        self.assertEqual(self.client.delete(url(draft)).status_code, 204)
        self.assertEqual(list(ClinicalDocument.objects.values_list("title", flat=True)), ["Signed"])
        self.assertTrue(AuditEvent.objects.filter(action="document.delete", outcome="allowed").exists())


class ClientSessionTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.user = self.make_user()
        self.client_record, self.rel = self.link(self.therapist, self.user)
        self.day = timezone.localdate() + timedelta(days=3)

    def test_client_sees_upcoming_and_cancelled_sessions_only_from_active_care(self):
        upcoming = Session.objects.create(client=self.client_record, therapist=self.therapist, date=self.day,
                                          start_time=time(10, 0), status="scheduled")
        cancelled = Session.objects.create(client=self.client_record, therapist=self.therapist,
                                           date=self.day + timedelta(days=7), status="cancelled")
        Session.objects.create(client=self.client_record, therapist=self.therapist,
                               date=timezone.localdate() - timedelta(days=7))  # past
        self.login(self.user)
        data = self.client.get("/api/care-team/sessions/").data
        self.assertEqual([(s["id"], s["status"]) for s in data], [(upcoming.pk, "scheduled"), (cancelled.pk, "cancelled")])
        self.assertEqual(data[0]["therapist_name"], "Dana Lee")
        self.rel.status = "ended"
        self.rel.save()
        self.assertEqual(self.client.get("/api/care-team/sessions/").data, [])

    def test_client_is_emailed_with_a_calendar_file_when_sessions_change(self):
        from django.core import mail

        self.login(self.therapist)
        base = f"/api/practice/clients/{self.client_record.pk}/sessions/"
        res = self.client.post(base, {"date": self.day.isoformat(), "start_time": "10:00", "status": "scheduled",
                                      "repeat_weeks": 2}, format="json")
        self.assertTrue(res.data["client_notified"])
        sent = mail.outbox[-1]
        self.assertEqual(sent.to, [self.user.email])
        self.assertNotIn("therap", sent.subject.lower())  # neutral subject: it shows on lock screens
        self.assertIn("weekly for 3 sessions", sent.body)
        filename, ics, mimetype = sent.attachments[0]
        self.assertEqual((filename, mimetype), ("session.ics", "text/calendar"))
        self.assertEqual(ics.count("BEGIN:VEVENT"), 3)

        url = f"{base}{res.data['id']}/"
        self.assertTrue(self.client.patch(url, {"start_time": "11:30"}, format="json").data["client_notified"])
        self.assertIn("moved your session", mail.outbox[-1].body)
        self.assertTrue(self.client.patch(url, {"status": "cancelled"}, format="json").data["client_notified"])
        self.assertIn("cancelled", mail.outbox[-1].subject)
        self.assertIn("STATUS:CANCELLED", mail.outbox[-1].attachments[0][1])

        count = len(mail.outbox)
        past = (timezone.localdate() - timedelta(days=2)).isoformat()
        self.client.post(base, {"date": past, "status": "completed"}, format="json")  # recording history: no email
        self.assertEqual(len(mail.outbox), count)
