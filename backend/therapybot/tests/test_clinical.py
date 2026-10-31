"""Phase 3: the therapist's record, AI assistance with validated citations, and the note lifecycle."""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from therapybot.clinical.citations import label_chunks, validate_items, validate_text
from therapybot.models import AuditEvent, ClinicalDocument, Plan, Session, TreatmentPlan
from therapybot.rag import RetrievedChunk
from therapybot.tests.helpers import APITestCase


def chunk(i, text="note text"):
    return RetrievedChunk(chunk_id=i, text=text, score=0, document_id=i, session_id=None,
                          session_date="2026-10-01", doc_type="progress_note")


class CitationValidationTests(APITestCase):
    def test_items_without_a_real_source_are_dropped(self):
        sources = label_chunks([chunk(1), chunk(2)])
        kept, dropped = validate_items(
            [
                {"text": "Practiced worry time", "sources": ["S1"]},
                {"text": "Mentioned a 2019 hospitalization", "sources": ["S9"]},  # invented label
                {"text": "No citation at all", "sources": []},
                {"text": "Mixed", "sources": ["[S2]", "S7"]},
                "not a dict",
            ],
            sources,
        )
        self.assertEqual(kept, [{"text": "Practiced worry time", "sources": ["S1"]}, {"text": "Mixed", "sources": ["S2"]}])
        self.assertEqual(dropped, 2)

    def test_invented_markers_are_removed_from_prose(self):
        sources = label_chunks([chunk(1)])
        text, cited = validate_text("Sleep improved [S1]. GAD-7 was 22 [S4].", sources)
        self.assertEqual((text, cited), ("Sleep improved [S1]. GAD-7 was 22.", ["S1"]))


class RecordTestCase(APITestCase):
    """A therapist (Dr Lee) with one synthetic client (Sam) who has two sessions of notes."""

    def setUp(self):
        super().setUp()
        self.lee = self.make_therapist()
        self.sam = self.make_user("sam", "sam@example.com")
        self.record, self.rel = self.link(self.lee, self.sam)
        today = timezone.localdate()
        self.s1 = Session.objects.create(client=self.record, therapist=self.lee, date=today - timedelta(days=14), modality="cbt")
        self.s2 = Session.objects.create(client=self.record, therapist=self.lee, date=today - timedelta(days=7), modality="cbt")
        self.n1 = self.note(self.s1, "Introduced thought records for work anxiety. Sleep 5 hours.")
        self.n2 = self.note(self.s2, "Reviewed thought records; catastrophizing about deadlines. Plan: worry time at 6pm.")
        self.login(self.lee)
        self.base = f"/api/practice/clients/{self.record.pk}"

    def note(self, session, text, status="final"):
        return ClinicalDocument.objects.create(client=self.record, author=self.lee, session=session,
                                               session_date=session.date, doc_type="progress_note",
                                               status=status, title="Progress note", text=text)


class PrepTests(RecordTestCase):
    @mock.patch("therapybot.clinical.assistant.complete_json")
    def test_prep_cites_real_sessions_and_drops_invented_ones(self, complete):
        complete.return_value = {
            "summary": "Working on catastrophizing [S1] after a 2019 hospitalization [S9].",
            "last_session": [{"text": "Reviewed thought records", "sources": ["S1"]},
                             {"text": "Discussed medication changes", "sources": ["S8"]}],
            "open_threads": [{"text": "Sleep still short", "sources": ["S2"]}],
            "suggested_focus": [{"text": "Start worry time", "sources": ["S1"]}],
        }
        res = self.client.post(f"{self.base}/prep/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertNotIn("[S9]", res.data["summary"])
        self.assertEqual([i["text"] for i in res.data["last_session"]], ["Reviewed thought records"])
        self.assertEqual(res.data["dropped_claims"], 1)
        cited_docs = {s["document_id"] for s in res.data["sources"]}
        self.assertTrue(cited_docs <= {self.n1.pk, self.n2.pk} and cited_docs)
        facts = res.data["facts"]
        self.assertEqual((facts["sessions_completed"], facts["last_session_date"]), (2, self.s2.date.isoformat()))
        # The model only ever saw this client's record
        prompt = complete.call_args.args[0][1].content
        self.assertIn("catastrophizing", prompt)
        event = AuditEvent.objects.filter(action="ai.prep").latest("created_at")
        self.assertNotIn("catastrophizing", str(event.metadata))

    @mock.patch("therapybot.clinical.assistant.complete_json")
    def test_homework_completion_follows_the_clients_sharing_choice(self, complete):
        complete.return_value = {}
        plan = Plan.objects.create(user=self.sam, client=self.record, assigned_by=self.lee, title="Worry time")
        step = plan.steps.create(title="Worry time at 6pm", frequency="daily")
        step.check_ins.create(date=timezone.localdate())
        hw = self.client.post(f"{self.base}/prep/").data["facts"]["homework"][0]
        self.assertEqual((hw["done_last_14_days"], hw["due_last_14_days"]), (1, 14))
        self.rel.share_checkins = False
        self.rel.save()
        hw = self.client.post(f"{self.base}/prep/").data["facts"]["homework"][0]
        self.assertNotIn("done_last_14_days", hw)


class AskTests(RecordTestCase):
    def ask(self, answer, question="What homework was assigned?"):
        model = mock.MagicMock()
        model.complete.return_value = answer
        with mock.patch("therapybot.llm.get_chat_model", return_value=model):
            return self.client.post(f"{self.base}/ask/", {"question": question}, format="json"), model

    def test_answers_keep_only_real_citations(self):
        res, _ = self.ask("Worry time at 6pm [S1]. Also lithium [S12].")
        self.assertEqual(res.data["answer"], "Worry time at 6pm [S1]. Also lithium.")
        self.assertEqual(len(res.data["sources"]), 1)

    def test_uncited_answers_are_not_presented_as_the_record(self):
        res, _ = self.ask("They're probably doing great overall.")
        self.assertEqual(res.data["answer"], "I couldn't find that in this client's record.")

    def test_empty_record_never_calls_the_model(self):
        ClinicalDocument.objects.filter(client=self.record).delete()
        res, model = self.ask("anything")
        self.assertEqual(res.data["sources"], [])
        model.complete.assert_not_called()


class NoteLifecycleTests(RecordTestCase):
    @mock.patch("therapybot.clinical.assistant.complete_json")
    def test_draft_from_transcript_saves_draft_and_source(self, complete):
        complete.return_value = {"sections": {"data": "Client reported stress.", "assessment": "Improving.",
                                              "plan": "Continue worry time."}, "review_flags": []}
        self.lee.profile.note_format = "dap"
        self.lee.profile.save()
        transcript = "Therapist: How was the week? Client: Stressful, and I had thoughts of suicide on Tuesday."
        res = self.client.post(f"{self.base}/draft-note/", {"source_text": transcript, "session": self.s2.pk},
                               format="json")
        self.assertEqual(res.status_code, 201, res.data)
        doc = ClinicalDocument.objects.get(pk=res.data["document"]["id"])
        self.assertEqual((doc.status, doc.session, doc.doc_type), ("draft", self.s2, "progress_note"))
        self.assertIn("## Data", doc.text)
        self.assertIn("(AI draft)", doc.title)
        self.assertTrue(ClinicalDocument.objects.filter(doc_type="transcript", session=self.s2).exists())
        self.assertIn("suicide or self-harm", res.data["review_flags"][0])  # added by code, not left to the model

    def test_sign_then_only_addenda(self):
        draft = self.note(self.s2, "Draft text", status="draft")
        url = f"{self.base}/documents/{draft.pk}/"
        self.assertEqual(self.client.patch(url, {"text": "Edited draft"}, format="json").status_code, 200)
        signed = self.client.post(f"{url}sign/").data
        self.assertEqual((signed["status"], signed["signed_by_name"]), ("final", "Dana Lee"))
        self.assertEqual(self.client.patch(url, {"text": "Sneaky edit"}, format="json").status_code, 409)
        draft.refresh_from_db()
        self.assertEqual(draft.text, "Edited draft")
        addendum = self.client.post(f"{url}addendum/", {"text": "Correction: sleep was 6 hours."}, format="json").data
        self.assertEqual((addendum["status"], addendum["amends"]), ("draft", draft.pk))

    def test_client_uploads_are_visible_but_not_editable(self):
        upload = ClinicalDocument.objects.create(owner=self.sam, author=self.sam, title="My summary", text="AVS text")
        timeline = self.client.get(f"{self.base}/timeline/").data
        self.assertIn(upload.pk, [d["id"] for d in timeline["other_documents"]])
        self.assertEqual([s["id"] for s in timeline["sessions"]], [self.s2.pk, self.s1.pk])
        self.assertEqual(self.client.get(f"{self.base}/documents/{upload.pk}/").data["text"], "AVS text")
        self.assertEqual(self.client.patch(f"{self.base}/documents/{upload.pk}/", {"text": "x"}, format="json").status_code, 409)


class TreatmentPlanTests(RecordTestCase):
    @mock.patch("therapybot.clinical.assistant.complete_json")
    def test_draft_keeps_only_evidenced_goals_then_sign(self, complete):
        complete.return_value = {
            "problem_summary": "Work-related anxiety [S1].",
            "goals": [
                {"text": "Reduce work anxiety", "sources": ["S1"],
                 "objectives": [{"text": "Use thought records 4x/week", "measure": "self-report",
                                 "interventions": ["Cognitive restructuring"]}]},
                {"text": "Address substance use", "sources": ["S5"], "objectives": []},  # no such source
            ],
        }
        res = self.client.post(f"{self.base}/treatment-plans/", {"modality": "cbt"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual([g["text"] for g in res.data["goals"]], ["Reduce work anxiety"])
        self.assertTrue(res.data["goals"][0]["evidence"][0]["document_id"])
        plan_url = f"{self.base}/treatment-plans/{res.data['id']}/"
        edit = {"goals": [{"text": "Reduce work anxiety", "objectives": [{"text": "Thought records 5x/week",
                                                                            "measure": "log", "interventions": []}]}]}
        edited = self.client.patch(plan_url, edit, format="json").data
        self.assertEqual(edited["goals"][0]["objectives"][0]["text"], "Thought records 5x/week")
        self.assertTrue(edited["goals"][0]["evidence"])  # evidence kept for an unchanged goal
        old = TreatmentPlan.objects.create(client=self.record, therapist=self.lee, status="active")
        self.assertEqual(self.client.post(f"{plan_url}sign/").data["status"], "active")
        old.refresh_from_db()
        self.assertEqual(old.status, "archived")
        self.assertEqual(self.client.patch(plan_url, edit, format="json").status_code, 409)


class HomeworkTests(RecordTestCase):
    def test_assigned_homework_appears_in_the_clients_plans(self):
        res = self.client.post(f"{self.base}/homework/", {
            "title": "Between sessions", "steps": [{"title": "Thought record", "frequency": "daily"}],
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.login(self.sam)
        plans = self.client.get("/api/plans/").data
        self.assertEqual([p["title"] for p in plans], ["Between sessions"])


class ClinicalAccessTests(RecordTestCase):
    def test_every_record_endpoint_hides_the_client_from_other_therapists(self):
        kim = self.make_therapist("drkim", "drkim@example.com")
        self.login(kim)
        calls = [
            ("get", "timeline/"), ("post", "sessions/"), ("post", "documents/"), ("get", f"documents/{self.n1.pk}/"),
            ("patch", f"documents/{self.n1.pk}/"), ("post", f"documents/{self.n1.pk}/sign/"),
            ("post", f"documents/{self.n1.pk}/addendum/"), ("get", "homework/"), ("post", "prep/"),
            ("post", "ask/"), ("post", "draft-note/"), ("get", "treatment-plans/"),
        ]
        for method, path in calls:
            with self.subTest(path=path):
                res = getattr(self.client, method)(f"{self.base}/{path}", {"question": "x"}, format="json")
                self.assertEqual(res.status_code, 404)

    def test_clients_cannot_use_record_endpoints(self):
        self.login(self.sam)
        self.assertEqual(self.client.get(f"{self.base}/timeline/").status_code, 403)


class JsonRobustnessTests(APITestCase):
    def test_malformed_json_is_retried_once_in_json_mode(self):
        from therapybot.ai.drafting import complete_json

        model = mock.MagicMock()
        model.complete.side_effect = ['{"a": 1,, }', '{"a": 1}']
        with mock.patch("therapybot.llm.get_chat_model", return_value=model):
            self.assertEqual(complete_json([], "Test"), {"a": 1})
        self.assertEqual(model.complete.call_count, 2)
        self.assertTrue(model.complete.call_args.kwargs["json_mode"])
        model.complete.side_effect = ["not json", "still not"]
        with mock.patch("therapybot.llm.get_chat_model", return_value=model), self.assertRaises(ValueError):
            complete_json([], "Test")


class MarkerNormalizationTests(APITestCase):
    def test_variant_citation_formats_are_understood(self):
        sources = label_chunks([chunk(1), chunk(2)])
        for raw, expected in [
            ("GAD-7 was 14【S1】", "GAD-7 was 14[S1]"),
            ("Two facts [S1, S2].", "Two facts [S1][S2]."),
            ("Spaced [ S2 ] marker", "Spaced [S2] marker"),
            ("Full-width ［S1］ too", "Full-width [S1] too"),
            ("GAD\u20117\u202f9 [S1]", "GAD\u20117 9 [S1]"),
        ]:
            with self.subTest(raw=raw):
                text, cited = validate_text(raw, sources)
                self.assertEqual(text, expected)
                self.assertTrue(cited)
        kept, _ = validate_items([{"text": "x", "sources": ["【S2】", " s1 "]}], sources)
        self.assertEqual(kept[0]["sources"], ["S2", "S1"])


class CitationEdgeCaseTests(APITestCase):
    def test_zero_width_characters_inside_markers_still_count(self):
        sources = label_chunks([chunk(1)])
        self.assertEqual(validate_text("Intake GAD-7 was 15 [​S1].", sources), ("Intake GAD-7 was 15 [S1].", ["S1"]))
        kept, _ = validate_items([{"text": "x", "sources": ["​S1"]}], sources)
        self.assertEqual(kept[0]["sources"], ["S1"])

    def test_facts_citations_ground_an_answer_without_showing_a_marker(self):
        sources = label_chunks([chunk(1)])
        self.assertEqual(validate_text("Latest GAD-7 is 11 [FACTS].", sources), ("Latest GAD-7 is 11.", ["FACTS"]))
        kept, dropped = validate_items([{"text": "GAD-7 down 4 points", "sources": ["FACTS"]}], sources)
        self.assertEqual((kept[0]["sources"], dropped), (["FACTS"], 0))

    @mock.patch("therapybot.clinical.assistant.complete_json")
    def test_note_that_names_ideation_gets_a_risk_flag_even_without_keywords_in_the_source(self, complete):
        from therapybot.clinical import assistant

        complete.return_value = {"sections": {"assessment": "Passive suicidal ideation without a plan."}, "review_flags": []}
        therapist = self.make_therapist()
        client, _ = self.link(therapist, self.make_user())
        draft = assistant.draft_progress_note(actor=therapist, client=client, note_format="dap",
                                              source_text="C: Some nights maybe I shouldn't be here.")
        self.assertIn("suicide or self-harm", draft["review_flags"][0])
