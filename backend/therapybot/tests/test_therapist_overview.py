"""The client's page for one therapist: everything shared with them, never the therapist's private notes."""

from datetime import timedelta

from django.utils import timezone

from therapybot.models import (
    CareRelationship,
    ClinicalDocument,
    Plan,
    PlanStep,
    Session,
    TreatmentGoal,
    TreatmentObjective,
    TreatmentPlan,
)
from therapybot.tests.helpers import APITestCase


class TherapistOverviewTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.user = self.make_user()
        self.client_record, self.relationship = self.link(self.therapist, self.user)
        self.url = f"/api/care-team/{self.relationship.pk}/overview/"
        self.login(self.user)

    def doc(self, doc_type, text, status="final"):
        return ClinicalDocument.objects.create(client=self.client_record, author=self.therapist, doc_type=doc_type,
                                               text=text, status=status, signed_at=timezone.now())

    def plan(self, shared):
        plan = TreatmentPlan.objects.create(client=self.client_record, therapist=self.therapist, status="active",
                                            share_with_client=shared)
        goal = TreatmentGoal.objects.create(plan=plan, text="Feel calmer at work")
        TreatmentObjective.objects.create(goal=goal, text="Use worry time 5 days a week")
        return plan

    def test_shows_what_is_shared_and_never_private_notes(self):
        today = timezone.localdate()
        Session.objects.create(client=self.client_record, therapist=self.therapist, date=today - timedelta(days=7))
        Session.objects.create(client=self.client_record, therapist=self.therapist, status="scheduled",
                               date=today + timedelta(days=2))
        self.doc("progress_note", "PRIVATE clinical impressions")
        self.doc("client_summary", "We practiced slowing down your breathing.")
        self.doc("client_summary", "DRAFT summary", status="draft")
        homework = Plan.objects.create(user=self.user, client=self.client_record, assigned_by=self.therapist,
                                       title="Worry time")
        PlanStep.objects.create(plan=homework, title="15 minutes at 6pm")
        plan = self.plan(shared=False)

        data = self.client.get(self.url).data
        body = str(data)
        self.assertNotIn("PRIVATE", body)
        self.assertNotIn("DRAFT", body)
        self.assertEqual(data["therapist"]["practice_name"], self.client_record.practice.name)
        self.assertEqual((len(data["sessions"]), data["sessions_attended"], data["last_session"]),
                         (1, 1, today - timedelta(days=7)))
        self.assertEqual([s["text"] for s in data["summaries"]], ["We practiced slowing down your breathing."])
        self.assertEqual(data["homework"], [{"id": homework.id, "title": "Worry time", "steps": ["15 minutes at 6pm"]}])
        self.assertEqual(data["goals"], [])  # not shared

        plan.share_with_client = True
        plan.save()
        self.assertEqual(self.client.get(self.url).data["goals"],
                         [{"text": "Feel calmer at work", "objectives": ["Use worry time 5 days a week"]}])

    def test_only_the_client_sees_it_and_ended_care_shows_just_who(self):
        self.login(self.make_user("bob", "bob@example.com"))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.login(self.therapist)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.doc("client_summary", "Shared before care ended")
        self.relationship.status = CareRelationship.Status.ENDED
        self.relationship.save()
        self.login(self.user)
        data = self.client.get(self.url).data
        self.assertEqual(data["relationship"]["status"], "ended")
        self.assertNotIn("summaries", data)
