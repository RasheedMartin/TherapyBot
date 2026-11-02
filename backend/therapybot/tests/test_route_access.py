"""
Every route that takes an object id refuses anyone who doesn't own that object.

The sweep reads the URL conf, so a new route with an id is covered without anyone remembering to add it.
A route whose id this file doesn't know how to fill fails the test until a fixture is added for it.
"""

from datetime import date
from unittest import mock

from django.core.cache import cache
from django.urls import URLPattern, get_resolver

from therapybot.models import (
    ClinicalDocument, Conversation, Plan, PlanStep, RiskFlag, SavedProvider, ScreeningAssignment,
    ScreeningTemplate, Session, TreatmentPlan,
)
from therapybot.tests.helpers import APITestCase

METHODS = ("get", "post", "put", "patch", "delete")
REFUSED = {403, 404, 405}


def _routes():
    """(route, [int params]) for every API path with an <int:...> converter."""
    for pattern in get_resolver().url_patterns:
        if not str(pattern.pattern).startswith("api/"):
            continue
        for child in getattr(pattern, "url_patterns", [pattern]):
            if not isinstance(child, URLPattern):
                continue
            params = [name for name, conv in child.pattern.converters.items() if type(conv).__name__ == "IntConverter"]
            if params:
                yield "/api/" + str(child.pattern), params


class RouteAccessSweep(APITestCase):
    def setUp(self):
        super().setUp()
        # Owner side: therapist A and their client Alice, with one of everything
        self.therapist = self.make_therapist()
        self.alice = self.make_user()
        self.client_a, self.rel_a = self.link(self.therapist, self.alice)
        practice = self.client_a.practice
        session = Session.objects.create(client=self.client_a, therapist=self.therapist, date=date(2026, 10, 1))
        doc = ClinicalDocument.objects.create(client=self.client_a, author=self.therapist, session=session,
                                              doc_type="progress_note", status="draft", title="Note",
                                              text="Synthetic note about the subway.")
        plan = TreatmentPlan.objects.create(client=self.client_a, therapist=self.therapist)
        template = ScreeningTemplate.objects.create(practice=practice, name="Sleep", items=["Q1"],
                                                    options=[{"value": 0, "label": "No"}, {"value": 1, "label": "Yes"}])
        assignment = ScreeningAssignment.objects.create(client=self.client_a, assigned_by=self.therapist,
                                                        instrument="phq9", due_on=date(2026, 11, 1))
        flag = RiskFlag.objects.create(client=self.client_a, level="elevated", source_type="screening", reason="Item 9")
        conversation = Conversation.objects.create(user=self.alice)
        homework = Plan.objects.create(user=self.alice, title="Sleep")
        step = PlanStep.objects.create(plan=homework, title="Same wake-up time")
        upload = ClinicalDocument.objects.create(owner=self.alice, title="Visit", text="Synthetic visit summary.")
        provider = SavedProvider.objects.create(user=self.alice, npi="1801415708", details={"name": "Synthetic"})

        # Outsiders with real relationships of their own, so only ownership tells them apart
        self.other_therapist = self.make_therapist("drkim", "drkim@example.com")
        self.bob = self.make_user("bob", "bob@example.com")
        self.client_b, _ = self.link(self.other_therapist, self.bob)

        self.ids = {
            "/api/practice/clients/": {"pk": self.client_a.pk, "session_id": session.pk, "doc_id": doc.pk,
                                       "plan_id": plan.pk, "assignment_id": assignment.pk},
            "/api/practice/risk-flags/": {"flag_id": flag.pk},
            "/api/practice/screening-templates/": {"template_id": template.pk},
            "/api/care-team/": {"pk": self.rel_a.pk},
            "/api/conversations/": {"pk": conversation.pk},
            "/api/plans/": {"pk": homework.pk},
            "/api/plan-steps/": {"pk": step.pk},
            "/api/notes/": {"pk": upload.pk},
            "/api/saved-providers/": {"pk": provider.pk},
        }
        self.snapshot = self._state()

    def _state(self):
        models = (Session, ClinicalDocument, TreatmentPlan, ScreeningTemplate, ScreeningAssignment, RiskFlag,
                  Conversation, Plan, PlanStep, SavedProvider)
        return {m.__name__: sorted(m.objects.values_list("pk", "updated_at" if hasattr(m, "updated_at") else "pk"))
                for m in models}

    def _fill(self, route, params, overrides=None):
        prefix = next((p for p in self.ids if route.startswith(p)), None)
        values = {**self.ids.get(prefix, {}), **(overrides or {})}
        missing = [p for p in params if p not in values]
        self.assertFalse(missing, f"{route}: no fixture for {missing}; add one to RouteAccessSweep.ids")
        url = route
        for name in params:
            url = url.replace(f"<int:{name}>", str(values[name]))
        return url

    def _assert_refused(self, user, url):
        self.login(user)
        for method in METHODS:
            cache.clear()  # the sweep sends more requests than the per-user throttle allows
            res = getattr(self.client, method)(url, {}, format="json")
            self.assertIn(res.status_code, REFUSED, f"{method.upper()} {url} as {user.username}: {res.status_code}")

    @mock.patch("therapybot.llm.get_chat_model", side_effect=AssertionError("an outsider reached the model"))
    def test_outsiders_are_refused_on_every_route_with_an_id(self, _model):
        routes = list(_routes())
        self.assertGreater(len(routes), 30)
        for route, params in routes:
            outsider = self.other_therapist if route.startswith("/api/practice/") else self.bob
            self._assert_refused(outsider, self._fill(route, params))
        self.assertEqual(self._state(), self.snapshot)

    @mock.patch("therapybot.llm.get_chat_model", side_effect=AssertionError("an outsider reached the model"))
    def test_another_clients_records_cant_be_reached_through_your_own_client(self, _model):
        # Therapist B names their own client in the URL and A's objects after it
        for route, params in _routes():
            if route.startswith("/api/practice/clients/") and len(params) > 1:
                self._assert_refused(self.other_therapist, self._fill(route, params, {"pk": self.client_b.pk}))
        self.assertEqual(self._state(), self.snapshot)

    def test_the_owner_can_reach_the_same_urls(self):
        """Guards the sweep itself: if the fixtures were wrong, every request would 404 and prove nothing."""
        self.login(self.therapist)
        for route, params in _routes():
            if route.startswith("/api/practice/clients/") and route.endswith(("/timeline/", "/documents/<int:doc_id>/")):
                cache.clear()
                self.assertEqual(self.client.get(self._fill(route, params)).status_code, 200, route)
        self.login(self.alice)
        for route in ("/api/care-team/<int:pk>/overview/", "/api/notes/<int:pk>/", "/api/plans/<int:pk>/"):
            cache.clear()
            self.assertEqual(self.client.get(self._fill(route, ["pk"])).status_code, 200, route)
