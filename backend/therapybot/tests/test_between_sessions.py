"""Phase 6: the companion follows the therapist's plan, chat risk reaches the care team, shared summaries."""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.utils import timezone

from therapybot import between_sessions
from therapybot.models import (
    Conversation,
    Message,
    Plan,
    PlanStep,
    RiskFlag,
    Session,
    TreatmentGoal,
    TreatmentObjective,
    TreatmentPlan,
)
from therapybot.tests.helpers import APITestCase
from therapybot.views.chat import user_context


def chat_reply(risk):
    def reply(question, therapy_type, history, user_context, sources, assessment):
        assessment["risk"] = risk
        return ("I'm here with you.", risk == "imminent")
    return reply


def fast_model(text="They talked about work stress and tried worry time twice."):
    model = mock.MagicMock()
    model.complete.return_value = text
    return mock.patch("therapybot.llm.get_chat_model", return_value=model), model


class CompanionContextTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.user = self.make_user()

    def _treatment_plan(self, client, status="active"):
        plan = TreatmentPlan.objects.create(client=client, therapist=self.therapist, status=status)
        goal = TreatmentGoal.objects.create(plan=plan, text="Reduce work-related worry")
        TreatmentObjective.objects.create(goal=goal, text="Use scheduled worry time 5 days a week")

    def test_linked_client_gets_goals_session_and_homework_origin(self):
        client, _ = self.link(self.therapist, self.user)
        self._treatment_plan(client)
        self._treatment_plan(client, status="draft")  # unsigned drafts never reach the client
        TreatmentPlan.objects.filter(status="draft").first().goals.update(text="DRAFT GOAL")
        Session.objects.create(client=client, therapist=self.therapist, status="scheduled",
                               date=timezone.localdate() + timedelta(days=3))
        plan = Plan.objects.create(user=self.user, client=client, assigned_by=self.therapist, title="Worry time")
        PlanStep.objects.create(plan=plan, title="15 minutes of worry time")

        context = user_context(self.user)
        self.assertIn("Dana Lee", context)
        self.assertIn("Reduce work-related worry", context)
        self.assertIn("Use scheduled worry time", context)
        self.assertNotIn("DRAFT GOAL", context)
        self.assertIn("Next session:", context)
        self.assertIn("Worry time (from their therapist)", context)
        self.assertIn("safety alerts always", context)

    def test_unlinked_and_ended_clients_get_no_therapy_context(self):
        self.assertNotIn("therapist", user_context(self.user).lower())
        client, _ = self.link(self.therapist, self.user, status="ended")
        self._treatment_plan(client)
        self.assertNotIn("Reduce work-related worry", user_context(self.user))


class ChatRiskFlagTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.user = self.make_user()
        self.convo = Conversation.objects.create(user=self.user)
        self.login(self.user)

    def send(self, risk):
        with mock.patch("therapybot.ai.therapy_chat", side_effect=chat_reply(risk)):
            return self.client.post(f"/api/conversations/{self.convo.pk}/messages/", {"content": "feeling hopeless tonight"}, format="json")

    def test_risk_in_chat_flags_every_active_therapist_and_tells_the_client(self):
        client, _ = self.link(self.therapist, self.user, share_chat_summaries=False, share_checkins=False)
        other = self.make_therapist("drkim", "drkim@example.com")
        other_client, _ = self.link(other, self.user)
        res = self.send("elevated")
        self.assertTrue(res.data["care_team_notified"])
        flags = RiskFlag.objects.filter(source_type="chat")
        self.assertEqual({f.client_id for f in flags}, {client.pk, other_client.pk})
        self.assertEqual(flags.first().message.role, Message.Role.USER)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["drkim@example.com", "drlee@example.com"])
        self.assertNotIn("hopeless", mail.outbox[0].body)  # no chat content leaves in email

    def test_repeat_risk_is_deduplicated_unless_it_escalates(self):
        self.link(self.therapist, self.user)
        self.send("elevated")
        self.send("elevated")
        self.assertEqual(RiskFlag.objects.count(), 1)
        self.send("imminent")
        self.assertEqual(list(RiskFlag.objects.values_list("level", flat=True).order_by("id")),
                         ["elevated", "imminent"])
        RiskFlag.objects.update(acknowledged_at=timezone.now())
        self.send("elevated")
        self.assertEqual(RiskFlag.objects.count(), 3)

    def test_no_flag_without_risk_or_without_a_therapist(self):
        self.assertFalse(self.send("elevated").data["care_team_notified"])  # unlinked
        self.link(self.therapist, self.user, status="invited")
        self.assertFalse(self.send("imminent").data["care_team_notified"])  # invite not accepted
        self.assertFalse(RiskFlag.objects.exists())
        self.assertFalse(self.send("none").data["care_team_notified"])
        self.assertFalse(RiskFlag.objects.exists())

    def test_private_conversations_still_flag_risk(self):
        self.link(self.therapist, self.user, share_chat_summaries=False)
        self.convo.shared_with_care_team = False
        self.convo.save()
        self.assertTrue(self.send("elevated").data["care_team_notified"])


class BetweenSessionsTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.user = self.make_user()
        self.client_record, self.rel = self.link(self.therapist, self.user)
        self.convo = Conversation.objects.create(user=self.user, title="Work stress")
        Message.objects.create(conversation=self.convo, role="user", content="Deadlines again, tried worry time.")
        Message.objects.create(conversation=self.convo, role="assistant", content="Nice work trying it.")
        self.url = f"/api/practice/clients/{self.client_record.pk}/between-sessions/"
        self.login(self.therapist)

    def test_shared_summary_is_generated_once_and_visible_to_the_client(self):
        patch, model = fast_model()
        with patch:
            first = self.client.get(self.url).data
            self.client.get(self.url)
        self.assertEqual(model.complete.call_count, 1)  # cached until new messages arrive
        self.assertEqual(first["conversations"][0]["summary"], "They talked about work stress and tried worry time twice.")
        self.assertIsNone(first["conversations"][0]["messages"])  # raw chat is off by default
        self.login(self.user)
        detail = self.client.get(f"/api/conversations/{self.convo.pk}/").data
        self.assertEqual(detail["care_summary"], first["conversations"][0]["summary"])

    def test_flagged_conversations_are_marked_whatever_the_summary_says(self):
        self.convo.messages.filter(role="user").update(risk_level="elevated")
        patch, _ = fast_model("They talked about work.")  # a summary that omits the risk
        with patch:
            item = self.client.get(self.url).data["conversations"][0]
            chunk = between_sessions.summary_chunks(self.client_record, self.rel)[0]
        self.assertTrue(item["flagged"])
        self.assertTrue(chunk.text.startswith(between_sessions.FLAGGED_NOTE))

    def test_client_choices_limit_what_is_shared(self):
        patch, model = fast_model()
        self.convo.shared_with_care_team = False
        self.convo.save()
        with patch:
            self.assertEqual(self.client.get(self.url).data["conversations"], [])
            self.convo.shared_with_care_team = True
            self.convo.save()
            self.rel.share_chat_summaries = False
            self.rel.save()
            self.assertEqual(self.client.get(self.url).data["conversations"], [])
            self.rel.share_raw_chat = True
            self.rel.save()
            item = self.client.get(self.url).data["conversations"][0]
        self.assertIsNone(item["summary"])
        self.assertEqual([m["content"] for m in item["messages"]][0], "Deadlines again, tried worry time.")
        model.complete.assert_not_called()

    def test_only_conversations_since_the_last_session(self):
        Session.objects.create(client=self.client_record, therapist=self.therapist, date=timezone.localdate())
        Conversation.objects.filter(pk=self.convo.pk).update(updated_at=timezone.now() - timedelta(days=2))
        patch, _ = fast_model()
        with patch:
            data = self.client.get(self.url).data
        self.assertEqual((data["since"], data["conversations"]), (timezone.localdate().isoformat(), []))

    def test_other_therapists_and_clients_cannot_read_it(self):
        self.login(self.make_therapist("drkim", "drkim@example.com"))
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.rel.status = "ended"
        self.rel.save()
        self.login(self.therapist)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_summaries_are_citable_in_prep_only_with_consent(self):
        patch, _ = fast_model()
        with patch:
            chunks = between_sessions.summary_chunks(self.client_record, self.rel)
            self.assertEqual([c.doc_type for c in chunks], ["chat_summary"])
            self.rel.share_chat_summaries = False
            self.assertEqual(between_sessions.summary_chunks(self.client_record, self.rel), [])
            # Another person's conversations never appear in this client's sources
            other = self.make_user("bob", "bob@example.com")
            Conversation.objects.create(user=other, title="Bob").messages.create(role="user", content="x")
            self.rel.share_chat_summaries = True
            self.assertEqual(len(between_sessions.summary_chunks(self.client_record, self.rel)), 1)


class RiskDenialCheckTests(APITestCase):
    def test_softened_risk_needs_a_documented_assessment(self):
        from therapybot.clinical.assistant import unsupported_risk_denial
        from therapybot.clinical.citations import label_chunks
        from therapybot.rag import RetrievedChunk

        def src(text, doc_type="chat_summary"):
            return RetrievedChunk(chunk_id=1, text=text, score=0, document_id=None, session_id=None,
                                  session_date="2026-10-30", doc_type=doc_type)

        chat = label_chunks([src('The client said "everyone would be better off without me" and did not answer.')])
        note = label_chunks([src("Intake. Denies SI/HI. Safety plan reviewed.", "progress_note")])
        softened = "Passive suicidal thoughts (better off without me) with no clear plan or current intent"
        self.assertTrue(unsupported_risk_denial(softened, ["S1"], chat))
        self.assertFalse(unsupported_risk_denial(softened, ["S1"], note))  # the note documents the assessment
        self.assertFalse(unsupported_risk_denial("Said everyone would be better off without them; assess safety",
                                                 ["S1"], chat))
        self.assertFalse(unsupported_risk_denial("No homework plan was set", ["S1"], chat))  # not about risk
