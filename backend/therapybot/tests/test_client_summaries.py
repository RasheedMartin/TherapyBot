"""Session summaries written for the client, and sharing treatment plan goals."""

from unittest import mock

from django.core import mail

from therapybot.models import Chunk, ClinicalDocument, TreatmentPlan
from therapybot.tests.helpers import APITestCase
from therapybot.views.chat import user_context

RECAP = "We talked about speaking up in meetings. This week, try the worry plan at 6pm and one thought record."


class ClientSummaryTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.user = self.make_user()
        self.client_record, self.rel = self.link(self.therapist, self.user)
        self.note = ClinicalDocument.objects.create(
            client=self.client_record, author=self.therapist, doc_type="progress_note", status="final",
            title="Progress note", text="Assessment: GAD features. Plan: worry time at 6pm, thought records.",
        )
        self.base = f"/api/practice/clients/{self.client_record.pk}/documents"
        self.login(self.therapist)

    def draft(self, note=None):
        model = mock.MagicMock()
        model.complete.return_value = RECAP
        with mock.patch("therapybot.llm.get_chat_model", return_value=model):
            return self.client.post(f"{self.base}/{(note or self.note).pk}/client-summary/")

    def test_draft_from_a_signed_note_then_share_with_the_client(self):
        res = self.draft()
        self.assertEqual(res.status_code, 201)
        self.assertEqual((res.data["doc_type"], res.data["status"], res.data["summary_of"]),
                         ("client_summary", "draft", self.note.pk))
        self.assertEqual(self.draft().data["id"], res.data["id"])  # asking again returns the same draft
        summary = ClinicalDocument.objects.get(pk=res.data["id"])
        self.assertFalse(Chunk.objects.filter(document=summary).exists())  # not indexed for retrieval

        self.login(self.user)
        self.assertEqual(self.client.get("/api/care-team/summaries/").data, [])  # drafts stay with the therapist
        self.login(self.therapist)
        shared = self.client.post(f"{self.base}/{summary.pk}/sign/")
        self.assertTrue(shared.data["client_notified"])
        self.assertEqual(mail.outbox[-1].subject, "You have a new update")
        self.assertNotIn("worry", mail.outbox[-1].body)  # content stays in the app

        self.login(self.user)
        summaries = self.client.get("/api/care-team/summaries/").data
        self.assertEqual([s["text"] for s in summaries], [RECAP])
        self.assertIn(RECAP, user_context(self.user))  # the companion reinforces it
        self.rel.status = "ended"
        self.rel.save()
        self.assertEqual(self.client.get("/api/care-team/summaries/").data, [])

    def test_only_signed_progress_notes_can_be_summarized(self):
        draft_note = ClinicalDocument.objects.create(client=self.client_record, author=self.therapist,
                                                     doc_type="progress_note", status="draft", title="D", text="x")
        self.assertEqual(self.draft(draft_note).status_code, 409)


class ShareGoalsTests(APITestCase):
    def test_therapist_toggles_whether_goals_reach_the_client(self):
        therapist = self.make_therapist()
        client_record, _ = self.link(therapist, self.make_user())
        plan = TreatmentPlan.objects.create(client=client_record, therapist=therapist, status="active")
        self.assertFalse(plan.share_with_client)
        self.login(therapist)
        url = f"/api/practice/clients/{client_record.pk}/treatment-plans/{plan.pk}/share/"
        self.assertTrue(self.client.post(url, {"share": True}, format="json").data["share_with_client"])
        self.assertFalse(self.client.post(url, {"share": False}, format="json").data["share_with_client"])
        self.login(self.make_therapist("drkim", "drkim@example.com"))
        self.assertEqual(self.client.post(url, {"share": True}, format="json").status_code, 404)


class SummaryGuardTests(APITestCase):
    def test_crisis_line_is_kept_only_when_the_note_raises_risk(self):
        from therapybot.clinical import assistant

        therapist = self.make_therapist()
        client_record, _ = self.link(therapist, self.make_user())
        model = mock.MagicMock()
        model.complete.return_value = "You practiced speaking up.\n\nIf anything feels overwhelming, call or text 988."

        def draft(text):
            note = ClinicalDocument.objects.create(client=client_record, author=therapist, doc_type="progress_note",
                                                   status="final", title="N", text=text)
            with mock.patch("therapybot.llm.get_chat_model", return_value=model):
                return assistant.draft_client_summary(actor=therapist, client=client_record, note=note)

        self.assertNotIn("988", draft("Practiced speaking up in meetings."))
        self.assertIn("988", draft("Passive suicidal ideation; safety plan reviewed."))
