import json
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from therapybot import ai, llm, rag, safety
from therapybot.models import Conversation, Message, Plan, PlanStep, SavedProvider, SessionNote
from therapybot.verification import email_verification_token

from therapybot.tests.helpers import CONSENT, STRONG_PASSWORD, APITestCase


def fake_models(main=None, fast=None):
    """Patch the chat models: `main` answers replies and drafts, `fast` is the risk screener."""
    main = main or mock.MagicMock(name="main model")
    fast = fast or mock.MagicMock(name="fast model")
    return mock.patch("therapybot.llm.get_chat_model", side_effect=lambda **kw: fast if kw.get("fast") else main)


def screener(risk=None, error=False, **fields):
    model = mock.MagicMock(name="fast model")
    if error:
        model.complete.side_effect = RuntimeError("groq down")
    else:
        model.complete.return_value = json.dumps({"risk": risk, **fields})
    return model


class CrisisDetectionTests(TestCase):
    def test_detects_crisis_phrases(self):
        for text in ["I want to die", "I want to kill myself", "I've been cutting myself", "better off dead"]:
            self.assertTrue(ai.is_crisis_message(text), text)

    def test_ignores_ordinary_messages(self):
        for text in ["I'm stressed about exams", "my plant died", "how do I handle a difficult boss?",
                     "my grandpa died by suicide years ago"]:
            self.assertFalse(ai.is_crisis_message(text), text)

    def test_crisis_short_circuits_llm(self):
        main, fast = mock.MagicMock(), mock.MagicMock()
        with fake_models(main, fast):
            reply, is_crisis = ai.therapy_chat("I want to kill myself")
        self.assertTrue(is_crisis)
        self.assertIn("988", reply)
        main.complete.assert_not_called()
        fast.complete.assert_not_called()  # explicit intent never waits on the screener

    def test_screener_catches_indirect_risk(self):
        with fake_models(fast=screener("elevated")):
            self.assertEqual(safety.assess_risk("everyone would be better off without me"), "elevated")
        with fake_models(fast=screener("imminent")):
            self.assertEqual(safety.assess_risk("I took all my pills"), "imminent")

    def test_topic_mentions_are_at_least_elevated(self):
        # Grief after a suicide shouldn't get a canned crisis card, but it does get careful handling
        with fake_models(fast=screener("none")):
            self.assertEqual(safety.assess_risk("my grandpa died by suicide years ago"), "elevated")

    def test_screener_failure(self):
        with fake_models(fast=screener(error=True)):
            self.assertEqual(safety.assess_risk("work is stressful"), "none")  # fail open
            self.assertEqual(safety.assess_risk("I keep thinking about suicide"), "imminent")  # fail safe

    def test_harm_in_progress_gets_emergency_response(self):
        main = mock.MagicMock()
        with fake_models(main, screener("imminent", in_progress=True)):
            assessment = {}
            reply, is_crisis = ai.therapy_chat("I just took a whole bottle of pills", assessment=assessment)
        self.assertTrue(is_crisis and assessment["emergency"])
        self.assertIn("911", reply)
        self.assertIn("1-800-222-1222", reply)
        main.complete.assert_not_called()

    def test_elevated_risk_adds_safety_guidance(self):
        main = mock.MagicMock()
        main.complete.return_value = "I'm here with you."
        with fake_models(main, screener("elevated")), mock.patch("therapybot.rag.retrieve_context", return_value=""):
            assessment = {}
            reply, is_crisis = ai.therapy_chat("I won't be a problem much longer", assessment=assessment)
        self.assertFalse(is_crisis)
        self.assertEqual(assessment["risk"], "elevated")
        system_prompt = main.complete.call_args.args[0][0].content
        self.assertIn("988", system_prompt)


class KnowledgeBaseTests(TestCase):
    def test_articles_parse_with_titles_and_no_h1(self):
        docs = rag.load_knowledge_documents()
        self.assertGreater(len(docs), 0)
        for doc in docs:
            self.assertTrue(doc.metadata["title"])
            self.assertFalse(doc.text.startswith("# "), doc.id)
            self.assertNotIn("---", doc.text[:5])

    def test_refuses_to_index_error_pages(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bad.md").write_text("<html><title>403 Forbidden</title></html>" + " " * 300)
            with mock.patch("therapybot.rag.knowledge.KNOWLEDGE_DIR", Path(tmp)), self.assertRaises(ValueError):
                rag.load_knowledge_documents()

    def test_short_queries_skip_retrieval(self):
        with mock.patch("therapybot.rag.knowledge.get_index") as get_index:
            self.assertEqual(rag.retrieve_context("hi there"), "")
        get_index.assert_not_called()

    def test_markdown_sections_keep_their_heading_path(self):
        from therapybot.rag.chunking import embedding_text, split_markdown

        text = "Intro line\n\n## Sleep\nWind down.\n### Habits\nSame wake time.\n```\n# not a heading\n```\n## Stress\nBreathe."
        self.assertEqual(
            split_markdown(text),
            [
                ("Intro line", "/"),
                ("## Sleep\nWind down.", "/"),
                ("### Habits\nSame wake time.\n```\n# not a heading\n```", "/Sleep/"),
                ("## Stress\nBreathe.", "/"),
            ],
        )
        self.assertEqual(embedding_text("Body", {"title": "T", "url": "u"}), "title: T\nurl: u\n\nBody")


class ProviderInterfaceTests(TestCase):
    def test_groq_returns_answer_not_reasoning(self):
        from therapybot.llm.groq_chat import GroqChatModel

        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "test"}), mock.patch("groq.Groq") as client_cls:
            client = client_cls.return_value
            message = mock.MagicMock(content="  Hello, Sam!  ", reasoning="thinking about Sam")
            client.chat.completions.create.return_value.choices = [mock.MagicMock(message=message)]
            model = GroqChatModel("openai/gpt-oss-20b", temperature=0, max_tokens=50, timeout=5, max_retries=0)
            self.assertEqual(model.complete([llm.user("hi")]), "Hello, Sam!")
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(kwargs["reasoning_effort"], "low")


class AuthTests(APITestCase):
    def test_register_and_obtain_token(self):
        res = self.client.post(
            "/api/register/", {"username": "bob", "email": "Bob@Example.com", "password": STRONG_PASSWORD, **CONSENT}
        )
        self.assertEqual(res.status_code, 201, res.data)
        bob = User.objects.get(username="bob")
        self.assertEqual(bob.email, "bob@example.com")
        self.assertIsNotNone(bob.profile.terms_accepted_at)
        self.assertIsNotNone(bob.profile.age_confirmed_at)

        res = self.client.post("/api/token/", {"username": "bob", "password": STRONG_PASSWORD})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_register_rejects_weak_password_and_duplicates(self):
        self.make_user()
        res = self.client.post("/api/register/", {"username": "carol", "email": "c@example.com", "password": "123", **CONSENT})
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)

        res = self.client.post(
            "/api/register/", {"username": "ALICE", "email": "new@example.com", "password": STRONG_PASSWORD, **CONSENT}
        )
        self.assertIn("username", res.data)

        res = self.client.post(
            "/api/register/", {"username": "dave", "email": "alice@example.com", "password": STRONG_PASSWORD, **CONSENT}
        )
        self.assertIn("email", res.data)

    def test_register_requires_consent(self):
        res = self.client.post(
            "/api/register/",
            {"username": "erin", "email": "erin@example.com", "password": STRONG_PASSWORD,
             "confirm_age": False, "accept_terms": True},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirm_age", res.data)
        self.assertFalse(User.objects.filter(username="erin").exists())

    def test_current_user_requires_auth(self):
        self.assertEqual(self.client.get("/api/current_user/").status_code, 401)
        user = self.make_user()
        self.login(user)
        self.assertEqual(self.client.get("/api/current_user/").data["username"], "alice")

    def test_health(self):
        res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "ok")


@override_settings(FRONTEND_URL="https://app.example.com")
class PasswordResetTests(APITestCase):
    def test_forgot_password_sends_frontend_link(self):
        self.make_user()
        res = self.client.post("/api/forgot-password/", {"email": "ALICE@example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://app.example.com/reset-password?uid=", mail.outbox[0].body)

    def test_forgot_password_does_not_leak_accounts(self):
        res = self.client.post("/api/forgot-password/", {"email": "nobody@example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_password(self):
        user = self.make_user()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        res = self.client.post("/api/reset-password/", {"uid": uid, "token": token, "new_password": "abc"})
        self.assertEqual(res.status_code, 400)

        res = self.client.post(
            "/api/reset-password/", {"uid": uid, "token": token, "new_password": "brand-New-Pass-77"}
        )
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("brand-New-Pass-77"))

        # Token is single-use
        res = self.client.post(
            "/api/reset-password/", {"uid": uid, "token": token, "new_password": "another-Pass-88"}
        )
        self.assertEqual(res.status_code, 400)


class ConversationTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/conversations/").status_code, 401)

    def test_create_and_list(self):
        res = self.client.post("/api/conversations/", {"therapy_type": "Anxiety Support"})
        self.assertEqual(res.status_code, 201, res.data)
        res = self.client.get("/api/conversations/")
        self.assertEqual(len(res.data), 1)

    def test_rejects_unknown_therapy_type(self):
        res = self.client.post("/api/conversations/", {"therapy_type": "Astrology"})
        self.assertEqual(res.status_code, 400)

    def test_cannot_access_other_users_conversation(self):
        other = self.make_user("eve", "eve@example.com")
        convo = Conversation.objects.create(user=other)
        self.assertEqual(self.client.get(f"/api/conversations/{convo.pk}/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/api/conversations/{convo.pk}/messages/", {"content": "hi"}).status_code, 404
        )

    @mock.patch("therapybot.ai.therapy_chat", return_value=("Here is some support.", False))
    def test_send_message_persists_and_passes_history(self, therapy_chat):
        convo = Conversation.objects.create(user=self.user, therapy_type="Anxiety Support")
        Message.objects.create(conversation=convo, role="user", content="earlier question")
        Message.objects.create(conversation=convo, role="assistant", content="earlier answer")

        res = self.client.post(f"/api/conversations/{convo.pk}/messages/", {"content": "  I feel anxious at work  "})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual([m["role"] for m in res.data["messages"]], ["user", "assistant"])
        self.assertEqual(res.data["conversation"]["title"], "I feel anxious at work")

        therapy_chat.assert_called_once_with(
            "I feel anxious at work",
            "Anxiety Support",
            [("user", "earlier question"), ("assistant", "earlier answer")],
            "",
            [],
            assessment={},
        )
        self.assertEqual(convo.messages.count(), 4)

    @mock.patch("therapybot.ai.therapy_chat", side_effect=RuntimeError("groq down"))
    def test_ai_failure_returns_503_without_saving(self, _):
        convo = Conversation.objects.create(user=self.user)
        res = self.client.post(f"/api/conversations/{convo.pk}/messages/", {"content": "hello"})
        self.assertEqual(res.status_code, 503)
        self.assertEqual(convo.messages.count(), 0)

    def test_empty_message_rejected(self):
        convo = Conversation.objects.create(user=self.user)
        res = self.client.post(f"/api/conversations/{convo.pk}/messages/", {"content": "   "})
        self.assertEqual(res.status_code, 400)

    def test_rename_and_delete(self):
        convo = Conversation.objects.create(user=self.user)
        res = self.client.patch(f"/api/conversations/{convo.pk}/", {"title": "Work stress"}, format="json")
        self.assertEqual(res.data["title"], "Work stress")
        self.assertEqual(self.client.delete(f"/api/conversations/{convo.pk}/").status_code, 204)
        self.assertFalse(Conversation.objects.exists())


class StreamingTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)
        self.convo = Conversation.objects.create(user=self.user)

    def read_events(self, res):
        import json

        body = b"".join(res.streaming_content).decode()
        return [json.loads(line) for line in body.splitlines() if line]

    @mock.patch("therapybot.ai.therapy_chat_stream", return_value=iter(["That sounds ", "hard."]))
    def test_streams_deltas_then_saves(self, _):
        res = self.client.post(f"/api/conversations/{self.convo.pk}/messages/stream/", {"content": "rough day"})
        self.assertEqual(res.status_code, 200)
        events = self.read_events(res)
        self.assertEqual([e["type"] for e in events], ["delta", "delta", "done"])
        self.assertEqual(events[-1]["messages"][1]["content"], "That sounds hard.")
        self.assertEqual(self.convo.messages.count(), 2)

    @mock.patch("therapybot.ai.therapy_chat_stream", side_effect=RuntimeError("groq down"))
    def test_stream_error_saves_nothing(self, _):
        res = self.client.post(f"/api/conversations/{self.convo.pk}/messages/stream/", {"content": "hello"})
        self.assertEqual(self.read_events(res)[-1]["type"], "error")
        self.assertEqual(self.convo.messages.count(), 0)

    def test_stream_rejects_other_users_conversation(self):
        other = Conversation.objects.create(user=self.make_user("eve", "eve@example.com"))
        res = self.client.post(f"/api/conversations/{other.pk}/messages/stream/", {"content": "hi"})
        self.assertEqual(res.status_code, 404)


class ProfileAndAccountTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    def test_profile_created_lazily_and_updates(self):
        res = self.client.get("/api/profile/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], "alice@example.com")

        res = self.client.patch(
            "/api/profile/",
            {"display_name": "Al", "zip_code": "10001", "goals": "Sleep better", "email": "AL@example.com"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "al@example.com")
        self.assertEqual(self.client.get("/api/current_user/").data["display_name"], "Al")
        self.assertIn("Sleep better", self.user.profile.chat_context())

    def test_profile_validation(self):
        self.make_user("bob", "bob@example.com")
        res = self.client.patch("/api/profile/", {"zip_code": "abc", "email": "bob@example.com"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("zip_code", res.data)
        self.assertIn("email", res.data)

    def test_change_password(self):
        res = self.client.post(
            "/api/account/password/", {"current_password": "wrong", "new_password": "fresh-Meadow-91"}
        )
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            "/api/account/password/", {"current_password": STRONG_PASSWORD, "new_password": "fresh-Meadow-91"}
        )
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("fresh-Meadow-91"))

    def test_export_contains_conversations(self):
        convo = Conversation.objects.create(user=self.user, title="Work")
        Message.objects.create(conversation=convo, role="user", content="hello")
        res = self.client.get("/api/account/export/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment", res["Content-Disposition"])
        self.assertEqual(res.data["conversations"][0]["messages"][0]["content"], "hello")

    def test_delete_account_requires_password_and_cascades(self):
        Conversation.objects.create(user=self.user)
        self.assertEqual(self.client.post("/api/account/delete/", {"password": "nope"}).status_code, 400)
        self.assertEqual(self.client.post("/api/account/delete/", {"password": STRONG_PASSWORD}).status_code, 204)
        self.assertFalse(User.objects.filter(username="alice").exists())
        self.assertFalse(Conversation.objects.exists())


class EmailVerificationTests(APITestCase):
    def test_signup_sends_link_and_gates_features_until_verified(self):
        self.client.post(
            "/api/register/",
            {"username": "fay", "email": "fay@example.com", "password": STRONG_PASSWORD, **CONSENT},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verify-email?uid=", mail.outbox[0].body)

        fay = User.objects.get(username="fay")
        self.login(fay)
        self.assertFalse(self.client.get("/api/current_user/").data["email_verified"])
        self.assertEqual(self.client.get("/api/conversations/").status_code, 403)
        self.assertEqual(self.client.get("/api/profile/").status_code, 200)  # settings stay reachable

        uid = urlsafe_base64_encode(force_bytes(fay.pk))
        token = email_verification_token.make_token(fay)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post("/api/verify-email/", {"uid": uid, "token": token}).status_code, 200)
        # Single use: verifying changes the token's hash input
        self.assertEqual(self.client.post("/api/verify-email/", {"uid": uid, "token": token}).status_code, 400)

        fay.refresh_from_db()
        self.login(fay)
        self.assertEqual(self.client.get("/api/conversations/").status_code, 200)

    def test_changing_email_requires_reverification(self):
        user = self.make_user()
        self.login(user)
        self.client.patch("/api/profile/", {"email": "new@example.com"}, format="json")
        user.refresh_from_db()
        self.assertIsNone(user.profile.email_verified_at)
        self.assertEqual(mail.outbox[-1].to, ["new@example.com"])

    def test_resend(self):
        user = self.make_user(verified=False)
        self.login(user)
        self.assertEqual(self.client.post("/api/verify-email/resend/").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)


SAMPLE_PROVIDER = {
    "npi": "1801415708", "name": "Laila Abdelsalam", "credential": "PHD", "type": "psychologist",
    "type_label": "Psychologist", "specialty": "Psychologist, Clinical", "street": "224 W 35th St",
    "city": "New York", "state": "NY", "zip": "10001", "phone": "(716) 680-1234", "lat": 40.75, "lng": -73.99,
}


class FindCareTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    def test_search_validates_zip(self):
        self.assertEqual(self.client.get("/api/providers/?zip=abc").status_code, 400)

    @mock.patch("therapybot.providers.search_providers")
    def test_search(self, search):
        search.return_value = {"zip": "10001", "widened": False, "center": None, "providers": [SAMPLE_PROVIDER]}
        res = self.client.get("/api/providers/?zip=10001&types=psychologist,counselor")
        self.assertEqual(res.status_code, 200)
        search.assert_called_once_with("10001", ["psychologist", "counselor"])

    def test_normalizes_npi_records(self):
        from therapybot import providers

        record = {
            "number": "1", "enumeration_type": "NPI-1",
            "basic": {"first_name": "JANE", "last_name": "DOE", "credential": "L.C.S.W."},
            "taxonomies": [{"desc": "Social Worker, Clinical", "primary": True, "state": "NY"}],
            "addresses": [{"address_purpose": "LOCATION", "country_code": "US", "address_1": "1 MAIN ST",
                           "city": "NEW YORK", "state": "NY", "postal_code": "100011234",
                           "telephone_number": "2125551234"}],
        }
        p = providers._normalize(record, "social_worker")
        self.assertEqual((p["name"], p["credential"], p["street"], p["zip"], p["phone"]),
                         ("Jane Doe", "LCSW", "1 Main St", "10001", "(212) 555-1234"))
        record["taxonomies"][0]["desc"] = "Counselor, Addiction (Substance Use Disorder)"
        self.assertIsNone(providers._normalize(record, "counselor"))

    def test_shortlist(self):
        res = self.client.post("/api/saved-providers/", {"npi": "1801415708", "details": SAMPLE_PROVIDER},
                               format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertNotIn("npi", res.data["details"])
        again = self.client.post("/api/saved-providers/", {"npi": "1801415708", "details": SAMPLE_PROVIDER},
                                 format="json")
        self.assertEqual(again.data["id"], res.data["id"])

        res = self.client.patch(f"/api/saved-providers/{res.data['id']}/", {"status": "contacted", "notes": "Left VM"},
                                format="json")
        self.assertEqual(res.data["status"], "contacted")
        self.assertEqual(len(self.client.get("/api/saved-providers/").data), 1)


class PlanTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    def create_plan(self):
        return self.client.post("/api/plans/", {
            "title": "Calmer mornings",
            "steps": [
                {"title": "Box breathing", "frequency": "daily", "time_of_day": "07:30"},
                {"title": "Call a therapist", "frequency": "once"},
                {"title": "Long walk", "frequency": "weekly", "weekday": 5},
            ],
        }, format="json")

    def test_create_edit_and_check_in(self):
        res = self.create_plan()
        self.assertEqual(res.status_code, 201, res.data)
        plan = res.data
        breathing = plan["steps"][0]

        # Edit: keep step 1, drop step 2, add a new one
        res = self.client.put(f"/api/plans/{plan['id']}/", {
            "title": "Calmer mornings",
            "steps": [{**breathing, "title": "Box breathing x4"}, {"title": "Journal", "frequency": "weekdays"}],
        }, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([s["title"] for s in res.data["steps"]], ["Box breathing x4", "Journal"])
        self.assertEqual(res.data["steps"][0]["id"], breathing["id"])

        today = timezone.localdate().isoformat()
        res = self.client.post(f"/api/plan-steps/{breathing['id']}/check-in/", {"date": today})
        self.assertEqual(res.data["steps"][0]["check_ins"], [today])
        res = self.client.delete(f"/api/plan-steps/{breathing['id']}/check-in/", {"date": today}, format="json")
        self.assertEqual(res.data["steps"][0]["check_ins"], [])

    def test_weekly_requires_day(self):
        res = self.client.post("/api/plans/", {"title": "x", "steps": [{"title": "walk", "frequency": "weekly"}]},
                               format="json")
        self.assertEqual(res.status_code, 400)

    def test_calendar_export(self):
        plan_id = self.create_plan().data["id"]
        res = self.client.get(f"/api/plans/{plan_id}/calendar.ics")
        body = res.content.decode()
        self.assertEqual(res["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn("RRULE:FREQ=DAILY", body)
        self.assertIn("RRULE:FREQ=WEEKLY;BYDAY=SA", body)
        self.assertIn("T073000", body)
        self.assertEqual(body.count("BEGIN:VEVENT"), 3)

    def test_other_users_plans_are_hidden(self):
        plan_id = self.create_plan().data["id"]
        self.login(self.make_user("eve", "eve@example.com"))
        self.assertEqual(self.client.get(f"/api/plans/{plan_id}/").status_code, 404)
        step = PlanStep.objects.first()
        self.assertEqual(self.client.post(f"/api/plan-steps/{step.pk}/check-in/").status_code, 404)

    @mock.patch("therapybot.ai.draft_plan")
    def test_draft_from_conversation_drops_bad_steps(self, draft):
        draft.return_value = {
            "title": "Interview calm",
            "summary": "Feel steadier before interviews",
            "steps": [
                {"title": "Paced breathing", "frequency": "daily", "time_of_day": "08:00"},
                {"title": "Walk", "frequency": "weekly", "weekday": None},  # invalid: weekly without a day
                {"title": "Practice answers", "frequency": "bogus"},  # unknown frequency falls back to daily
            ],
        }
        convo = Conversation.objects.create(user=self.user)
        Message.objects.create(conversation=convo, role="user", content="I'm nervous about interviews")
        res = self.client.post("/api/plans/draft/", {"conversation": convo.pk})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([s["title"] for s in res.data["steps"]], ["Paced breathing", "Practice answers"])
        self.assertEqual(res.data["steps"][1]["frequency"], "daily")
        self.assertFalse(Plan.objects.exists())  # drafts aren't saved


class WorkflowTests(APITestCase):
    """Features that hand off to each other: plans <-> calendar, shortlist <-> plan steps, plans -> chat."""

    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)
        self.plan = self.client.post("/api/plans/", {
            "title": "Getting support",
            "steps": [
                {"title": "Evening walk", "frequency": "daily", "time_of_day": "19:00"},
                {"title": "Call a therapist", "frequency": "once", "action": "find_care"},
            ],
        }, format="json").data

    def test_calendar_feed_lifecycle(self):
        self.assertFalse(self.client.get("/api/account/calendar-feed/").data["enabled"])
        links = self.client.post("/api/account/calendar-feed/").data
        self.assertTrue(links["webcal_url"].startswith("webcal://"))
        self.assertIn("calendar.google.com", links["google_url"])

        feed_path = links["url"].split("testserver", 1)[1]
        self.client.force_authenticate(None)  # calendar apps fetch without logging in
        body = self.client.get(feed_path).content.decode()
        self.assertIn("SUMMARY:Evening walk", body)
        self.assertIn("RRULE:FREQ=DAILY", body)

        self.login(self.user)
        self.client.patch("/api/account/calendar-feed/", {"discreet": True}, format="json")
        self.client.force_authenticate(None)
        body = self.client.get(feed_path).content.decode()
        self.assertNotIn("Evening walk", body)
        self.assertIn("SUMMARY:Personal check-in", body)

        # Rotating the link kills the old one
        self.login(self.user)
        new_links = self.client.post("/api/account/calendar-feed/").data
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(feed_path).status_code, 404)
        self.assertEqual(self.client.get(new_links["url"].split("testserver", 1)[1]).status_code, 200)

    def test_contacting_a_provider_completes_find_care_step(self):
        saved = self.client.post("/api/saved-providers/", {"npi": "1801415708", "details": SAMPLE_PROVIDER},
                                 format="json").data
        self.client.patch(f"/api/saved-providers/{saved['id']}/", {"status": "contacted"}, format="json")
        steps = self.client.get(f"/api/plans/{self.plan['id']}/").data["steps"]
        self.assertEqual(len(steps[1]["check_ins"]), 1)  # the find_care step
        self.assertEqual(steps[0]["check_ins"], [])  # the walk is untouched

    def test_chat_context_includes_plan_and_shortlist(self):
        from therapybot.views import user_context

        self.client.post(f"/api/plan-steps/{self.plan['steps'][0]['id']}/check-in/")
        SavedProvider.objects.create(user=self.user, npi="1", details={"name": "Dr A"}, status="waitlist")
        context = user_context(self.user)
        self.assertIn("Evening walk (done 1 of the last 7 days, done today)", context)
        self.assertIn("Call a therapist (not done yet)", context)
        self.assertIn("1 on waitlist", context)


@override_settings(GOOGLE_CLIENT_ID="test-client.apps.googleusercontent.com")
class GoogleSignInTests(APITestCase):
    CLAIMS = {"email": "Gina@Gmail.com", "email_verified": True, "given_name": "Gina"}

    def post(self, **extra):
        with mock.patch("google.oauth2.id_token.verify_oauth2_token", return_value=self.CLAIMS) as verify:
            res = self.client.post("/api/auth/google/", {"credential": "jwt", **extra}, format="json")
        verify.assert_called_once()
        self.assertEqual(verify.call_args.args[2], "test-client.apps.googleusercontent.com")
        return res

    def test_new_user_must_consent_then_is_created_verified(self):
        res = self.post()
        self.assertEqual(res.status_code, 400)
        self.assertTrue(res.data["consent_required"])
        self.assertFalse(User.objects.exists())

        res = self.post(**CONSENT)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data["created"])
        user = User.objects.get(email="gina@gmail.com")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.profile.display_name, "Gina")
        self.assertIsNotNone(user.profile.email_verified_at)

        # The returned token works, and passwordless accounts can set a password without a current one
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(self.client.get("/api/current_user/").data["username"], "gina")
        res = self.client.post("/api/account/password/", {"new_password": "brand-New-Pass-77"})
        self.assertEqual(res.status_code, 200, res.data)

    def test_existing_account_is_linked_and_verified(self):
        user = self.make_user("gina", "gina@gmail.com", verified=False)
        res = self.post()
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["created"])
        user.refresh_from_db()
        self.assertIsNotNone(user.profile.email_verified_at)

    def test_rejects_invalid_token_and_unverified_google_email(self):
        with mock.patch("google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("bad")):
            self.assertEqual(self.client.post("/api/auth/google/", {"credential": "x"}).status_code, 400)
        with mock.patch("google.oauth2.id_token.verify_oauth2_token", return_value={**self.CLAIMS, "email_verified": False}):
            self.assertEqual(self.client.post("/api/auth/google/", {"credential": "x", **CONSENT}, format="json").status_code, 400)

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_disabled_without_client_id(self):
        self.assertIsNone(self.client.get("/api/config/").data["google_client_id"])
        self.assertEqual(self.client.post("/api/auth/google/", {"credential": "x"}).status_code, 404)

    def test_passwordless_delete_requires_typed_confirmation(self):
        res = self.post(**CONSENT)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(self.client.post("/api/account/delete/", {}).status_code, 400)
        self.assertEqual(self.client.post("/api/account/delete/", {"confirm": "DELETE"}).status_code, 204)


class ReminderTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)
        self.plan = self.client.post("/api/plans/", {
            "title": "Evenings",
            "steps": [
                {"title": "Evening walk", "frequency": "daily", "time_of_day": "19:00"},
                {"title": "Sunday reset", "frequency": "weekly", "weekday": 6},
            ],
        }, format="json").data
        self.client.patch("/api/profile/", {"reminders_enabled": True, "reminder_time": "08:00",
                                            "timezone": "America/New_York"}, format="json")

    def run_at(self, iso):
        from datetime import datetime

        from therapybot.reminders import send_due_reminders

        return send_due_reminders(now=datetime.fromisoformat(iso))

    def test_sends_once_per_day_in_users_time_zone(self):
        # 2026-10-30 is a Friday. 07:59 New York = 11:59 UTC: too early
        self.assertEqual(self.run_at("2026-10-30T11:59:00+00:00"), 0)
        self.assertEqual(self.run_at("2026-10-30T12:05:00+00:00"), 1)
        self.assertEqual(self.run_at("2026-10-30T12:20:00+00:00"), 0)  # already sent today
        email = mail.outbox[0]
        self.assertIn("Evening walk", email.body)
        self.assertNotIn("Sunday reset", email.body)  # not due on a Friday
        self.assertIn("List-Unsubscribe", email.extra_headers)
        self.assertEqual(len(email.alternatives), 1)

    def test_skips_outside_window_and_when_nothing_is_due(self):
        self.assertEqual(self.run_at("2026-10-30T20:00:00+00:00"), 0)  # 4pm local: too late for 8am
        step_id = self.plan["steps"][0]["id"]
        self.client.post(f"/api/plan-steps/{step_id}/check-in/", {"date": "2026-10-31"})
        self.assertEqual(self.run_at("2026-10-31T12:05:00+00:00"), 0)  # Saturday: walk already done

    def test_email_check_in_link(self):
        from datetime import date

        from therapybot.reminders import check_in_token

        step = PlanStep.objects.get(title="Evening walk")
        token = check_in_token(step, date(2026, 10, 30))
        self.client.force_authenticate(None)
        preview = self.client.get(f"/api/quick-check-in/?t={token}")
        self.assertEqual((preview.data["step"], preview.data["done"]), ("Evening walk", False))  # GET changes nothing
        res = self.client.post("/api/quick-check-in/", {"t": token})
        self.assertTrue(res.data["done"])
        self.assertEqual(self.client.post("/api/quick-check-in/", {"t": token + "x"}).status_code, 400)

    def test_one_click_unsubscribe(self):
        from therapybot.reminders import unsubscribe_token

        self.client.force_authenticate(None)
        res = self.client.post(f"/api/reminders/unsubscribe/?t={unsubscribe_token(self.user)}")
        self.assertEqual(res.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.reminders_enabled)

    def test_rejects_bad_time_zone(self):
        res = self.client.patch("/api/profile/", {"timezone": "Mars/Olympus"}, format="json")
        self.assertEqual(res.status_code, 400)


class RelatedReadingTests(APITestCase):
    def test_topic_gates(self):
        from therapybot.articles import passes_topic_gate

        suicide = "https://medlineplus.gov/suicide.html"
        self.assertFalse(passes_topic_gate(suicide, "my mom died and I can't focus"))
        self.assertTrue(passes_topic_gate("https://medlineplus.gov/bereavement.html", "my mom died"))
        self.assertTrue(passes_topic_gate("https://medlineplus.gov/teenmentalhealth.html", "my TEENAGER is struggling"))

    def test_medlineplus_html_to_markdown(self):
        from therapybot.articles import _to_markdown

        md = _to_markdown("<h3>What is stress?</h3><p>Stress is a feeling&nbsp;of <b>tension</b>.</p><ul><li>Sleep</li><li>Exercise</li></ul>")
        self.assertIn("## What is stress?", md)
        self.assertIn("Stress is a feeling of tension.", md)
        self.assertIn("- Sleep\n- Exercise", md)

    @mock.patch("therapybot.ai.therapy_chat_stream")
    def test_sources_saved_on_reply(self, stream):
        def fake_stream(content, therapy_type, history, user_context, sources, assessment=None):
            sources.append({"title": "Insomnia", "url": "https://medlineplus.gov/insomnia.html", "source": "MedlinePlus"})
            yield "Try writing worries down earlier."

        stream.side_effect = fake_stream
        user = self.make_user()
        self.login(user)
        convo = Conversation.objects.create(user=user)
        res = self.client.post(f"/api/conversations/{convo.pk}/messages/stream/", {"content": "can't sleep at night"})
        list(res.streaming_content)
        reply = convo.messages.get(role="assistant")
        self.assertEqual(reply.sources[0]["title"], "Insomnia")
        detail = self.client.get(f"/api/conversations/{convo.pk}/").data
        self.assertEqual(detail["messages"][1]["sources"][0]["url"], "https://medlineplus.gov/insomnia.html")


SAMPLE_EXPLANATION = {
    "title": "Session on worry",
    "summary": "You talked about worry at work and practiced noticing thinking traps.",
    "key_points": ["Worry spikes before meetings"],
    "terms": [{"term": "GAD", "meaning": "Generalized anxiety disorder: ongoing, hard-to-control worry."}],
    "homework": [
        {"title": "Fill in a thought record", "frequency": "daily", "time_of_day": "20:00"},
        {"title": "Bad step", "frequency": "weekly", "weekday": None},
    ],
    "questions": ["How do I know if the thought record is working?"],
}


class SessionNoteTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user()
        self.login(self.user)

    @mock.patch("therapybot.ai.explain_notes", return_value=SAMPLE_EXPLANATION)
    def test_paste_notes_and_get_explanation(self, explain):
        res = self.client.post("/api/notes/", {"text": "Pt reports GAD sx. HW: thought record nightly.",
                                               "session_date": "2026-10-28"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["title"], "Session on worry")
        self.assertEqual([h["title"] for h in res.data["explanation"]["homework"]], ["Fill in a thought record"])
        self.assertEqual(res.data["explanation"]["homework"][0]["time_of_day"], "20:00")
        self.assertEqual(len(self.client.get("/api/notes/").data), 1)
        self.assertEqual(len(self.client.get("/api/account/export/").data["session_notes"]), 1)

    @mock.patch("therapybot.ai.explain_notes", return_value=SAMPLE_EXPLANATION)
    def test_text_file_upload(self, explain):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile("visit.txt", b"Discussed sleep hygiene and worry time. Practice nightly.")
        res = self.client.post("/api/notes/", {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIn("sleep hygiene", explain.call_args.args[0])

    def test_scanned_pdf_and_bad_files_are_explained(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from pypdf import PdfWriter

        writer, buf = PdfWriter(), io.BytesIO()
        writer.add_blank_page(width=200, height=200)
        writer.write(buf)
        res = self.client.post("/api/notes/", {"file": SimpleUploadedFile("scan.pdf", buf.getvalue())}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("scanned", res.data["file"][0])
        res = self.client.post("/api/notes/", {"file": SimpleUploadedFile("photo.jpg", b"x")}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.post("/api/notes/", {"text": "hi"}, format="json").status_code, 400)

    @mock.patch("therapybot.ai.therapy_chat", return_value=("Happy to go through it.", False))
    @mock.patch("therapybot.ai.explain_notes", return_value=SAMPLE_EXPLANATION)
    def test_discuss_notes_in_chat(self, explain, chat):
        note_id = self.client.post("/api/notes/", {"text": "Pt reports GAD sx. HW: thought record nightly."},
                                   format="json").data["id"]
        convo = self.client.post(f"/api/notes/{note_id}/discuss/").data
        self.assertTrue(convo["title"].startswith("About: "))
        self.client.post(f"/api/conversations/{convo['id']}/messages/", {"content": "what does GAD mean?"})
        context = chat.call_args.args[3]
        self.assertIn("practiced noticing thinking traps", context)
        self.assertIn("Fill in a thought record", context)

    def test_other_users_notes_hidden(self):
        note = SessionNote.objects.create(user=self.make_user("eve", "eve@example.com"), title="x", original_text="y")
        self.assertEqual(self.client.get(f"/api/notes/{note.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/notes/{note.pk}/discuss/").status_code, 404)


class ConversationMemoryTests(APITestCase):
    @override_settings(CHAT_HISTORY_TURNS=2)  # history window of 4 messages
    @mock.patch("therapybot.ai.summarize_conversation", return_value="They are worried about a work deadline.")
    @mock.patch("therapybot.ai.therapy_chat", return_value=("Got it.", False))
    def test_older_messages_fold_into_summary(self, chat, summarize):
        user = self.make_user()
        self.login(user)
        convo = Conversation.objects.create(user=user)
        for i in range(7):  # 14 messages total
            self.client.post(f"/api/conversations/{convo.pk}/messages/", {"content": f"message {i}"})
        convo.refresh_from_db()
        summarize.assert_called_once()
        self.assertEqual(len(summarize.call_args.args[1]), 10)  # the 10 oldest messages
        self.assertEqual(convo.summarized_count, 10)
        self.client.post(f"/api/conversations/{convo.pk}/messages/", {"content": "and now?"})
        self.assertIn("worried about a work deadline", chat.call_args.args[3])

    @mock.patch("therapybot.ai.therapy_chat_stream")
    def test_risk_level_is_saved_and_returned(self, stream):
        def fake_stream(content, therapy_type, history, user_context, sources, assessment=None):
            assessment["risk"] = "elevated"
            yield "I'm really glad you told me."

        stream.side_effect = fake_stream
        user = self.make_user()
        self.login(user)
        convo = Conversation.objects.create(user=user)
        res = self.client.post(f"/api/conversations/{convo.pk}/messages/stream/", {"content": "what's the point"})
        list(res.streaming_content)
        self.assertEqual(list(convo.messages.values_list("risk_level", flat=True)), ["elevated", "elevated"])
        self.assertEqual(self.client.get(f"/api/conversations/{convo.pk}/").data["messages"][1]["risk_level"], "elevated")


class SuggestedActionTests(APITestCase):
    def run_turn(self, risk, next_step):
        def fake_stream(content, therapy_type, history, user_context, sources, assessment=None):
            assessment.update(risk=risk, next_step=next_step if risk == "none" else "")
            yield "Okay."

        user = self.make_user(f"u{risk}", f"{risk}@example.com")
        self.login(user)
        convo = Conversation.objects.create(user=user)
        with mock.patch("therapybot.ai.therapy_chat_stream", side_effect=fake_stream):
            list(self.client.post(f"/api/conversations/{convo.pk}/messages/stream/", {"content": "hi"}).streaming_content)
        return convo.messages.get(role="assistant")

    def test_action_saved_for_safe_messages_only(self):
        self.assertEqual(self.run_turn("none", "find_care").suggested_action, "find_care")
        self.assertEqual(self.run_turn("elevated", "find_care").suggested_action, "")
