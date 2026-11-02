"""Check-ins a therapist sends: the client completes them from their portal, once or on a repeat."""

from datetime import date, timedelta

from django.core import mail
from django.utils import timezone

from therapybot.clinical import checkins
from therapybot.models import CareRelationship, RiskFlag, Screening, ScreeningAssignment
from therapybot.tests.helpers import APITestCase


class CheckInTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.client_user = self.make_user()
        self.client_record, self.relationship = self.link(self.therapist, self.client_user)
        self.base = f"/api/practice/clients/{self.client_record.pk}/checkins/"

    def assign(self, **data):
        self.login(self.therapist)
        return self.client.post(self.base, {"instrument": "phq9", "repeat": "once", **data}, format="json")

    def open_checkins(self):
        self.login(self.client_user)
        return self.client.get("/api/screenings/checkins/").data

    def complete(self, assignment_id, responses):
        self.login(self.client_user)
        return self.client.post("/api/screenings/mine/", {"assignment": assignment_id, "responses": responses},
                                format="json")

    def test_a_one_time_check_in_is_emailed_completed_and_closed(self):
        res = self.assign(note="Before Thursday, please")
        self.assertEqual((res.status_code, res.data["emailed"]), (201, True))
        self.assertEqual(len(mail.outbox), 1)
        # The inbox isn't private: no screening name or note in the email
        self.assertNotIn("PHQ", mail.outbox[0].body)
        self.assertNotIn("Thursday", mail.outbox[0].body)

        [open_one] = self.open_checkins()
        self.assertEqual((open_one["due"], open_one["note"], open_one["instrument"]["key"]),
                         (True, "Before Thursday, please", "phq9"))
        self.assertEqual(open_one["relationship"], self.relationship.pk)

        done = self.complete(open_one["id"], [1] * 8 + [2])
        self.assertEqual((done.status_code, done.data["flagged"]), (201, True))
        self.assertIn("support_message", done.data)
        self.assertEqual(Screening.objects.get().source, Screening.Source.SELF_REPORT)
        self.assertTrue(RiskFlag.objects.exists())
        self.assertEqual(self.open_checkins(), [])
        self.assertEqual(self.complete(open_one["id"], [0] * 9).status_code, 404)  # can't submit twice

    def test_repeating_check_in_moves_to_its_next_date(self):
        assignment_id = self.assign(repeat="weekly").data["id"]
        self.assertEqual(self.complete(assignment_id, [0] * 9).status_code, 201)
        [upcoming] = self.open_checkins()
        self.assertEqual((upcoming["due"], upcoming["due_on"]), (False, timezone.localdate() + timedelta(days=7)))
        self.assertEqual(self.complete(assignment_id, [0] * 9).status_code, 404)  # not open until then

    def test_missed_rounds_dont_stack_up(self):
        assignment = ScreeningAssignment(due_on=date(2026, 1, 5), repeat="biweekly")
        assignment.client, assignment.assigned_by, assignment.instrument = self.client_record, self.therapist, "gad7"
        assignment.save()
        checkins.complete(assignment, today=date(2026, 2, 10))
        self.assertEqual(assignment.due_on, date(2026, 2, 16))
        self.assertEqual(checkins.step(date(2026, 1, 31), "monthly"), date(2026, 2, 28))

    def test_daily_notices_go_once_per_due_date(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        res = self.assign(repeat="weekly", due_on=tomorrow.isoformat())
        self.assertEqual((res.data["emailed"], len(mail.outbox)), (False, 0))  # not due yet
        self.assertEqual(checkins.send_due_notices(today=tomorrow), 1)
        self.assertEqual(checkins.send_due_notices(today=tomorrow), 0)

    def test_validation_and_stopping(self):
        self.assertEqual(self.assign(instrument="t999").status_code, 400)
        self.assertEqual(self.assign(due_on="2020-01-01").status_code, 400)
        first = self.assign(repeat="monthly").data["id"]
        self.assertEqual(self.assign().status_code, 400)  # already sent
        self.assertEqual(self.client.delete(f"{self.base}{first}/").status_code, 204)
        self.assertEqual(self.open_checkins(), [])
        self.assertEqual(self.assign().status_code, 201)  # can send again once stopped

    def test_ending_care_hides_check_ins_and_others_cant_complete_them(self):
        assignment_id = self.assign().data["id"]
        stranger = self.make_user("bob", "bob@example.com")
        self.login(stranger)
        res = self.client.post("/api/screenings/mine/", {"assignment": assignment_id, "responses": [0] * 9},
                               format="json")
        self.assertEqual(res.status_code, 404)

        self.relationship.status = CareRelationship.Status.ENDED
        self.relationship.save()
        self.assertEqual(self.open_checkins(), [])
        self.assertEqual(self.complete(assignment_id, [0] * 9).status_code, 404)

    def test_archiving_a_template_stops_its_check_ins(self):
        self.login(self.therapist)
        template = self.client.post("/api/practice/screening-templates/", {
            "name": "Sleep", "items": ["Rested?"],
            "options": [{"value": 0, "label": "No"}, {"value": 1, "label": "Yes"}],
        }, format="json").data
        self.assertEqual(self.assign(instrument=template["key"]).status_code, 201)
        self.client.delete(f"/api/practice/screening-templates/{template['id']}/")
        self.assertEqual(self.open_checkins(), [])
