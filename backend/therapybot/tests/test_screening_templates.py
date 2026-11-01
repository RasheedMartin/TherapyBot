"""A practice's own screening templates: built, validated, scored, flagged and trended like PHQ-9."""

from therapybot.models import RiskFlag, ScreeningTemplate
from therapybot.tests.helpers import APITestCase

AGREE = [{"value": 0, "label": "Strongly disagree"}, {"value": 1, "label": "Disagree"}, {"value": 2, "label": "Neutral"},
         {"value": 3, "label": "Agree"}, {"value": 4, "label": "Strongly agree"}]
SLEEP = {
    "name": "Weekly sleep check-in",
    "prompt": "Think about the past week.",
    "items": ["I fell asleep within 30 minutes", "I woke up during the night", "I felt rested in the morning"],
    "options": AGREE,
    "bands": [{"min": 0, "label": "low"}, {"min": 6, "label": "medium"}, {"min": 10, "label": "high"}],
}


class ScreeningTemplateTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.client_record, _ = self.link(self.therapist, self.make_user())
        self.login(self.therapist)

    def create(self, **overrides):
        return self.client.post("/api/practice/screening-templates/", {**SLEEP, **overrides}, format="json")

    def record(self, key, responses):
        return self.client.post(f"/api/practice/clients/{self.client_record.pk}/screenings/",
                                {"instrument": key, "responses": responses}, format="json")

    def test_validation(self):
        self.assertIn("options", self.create(options=[{"value": 2, "label": "a"}, {"value": 1, "label": "b"}]).data)
        self.assertIn("items", self.create(items=[]).data)
        self.assertIn("risk_item", self.create(risk_item=9).data)
        self.assertIn("risk_min", self.create(risk_item=0, risk_min=7).data)

    def test_custom_scale_scoring_bands_trends_and_safety_flag(self):
        key = self.create(risk_item=1, risk_min=3).data["key"]
        instruments = {i["key"]: i for i in self.client.get("/api/screenings/instruments/").data}
        self.assertEqual((instruments[key]["max_total"], instruments[key]["custom"]), (12, True))

        res = self.record(key, [4, 2, 1])
        self.assertEqual((res.status_code, res.data["total"], res.data["severity"], res.data["flagged"]),
                         (201, 7, "medium", False))
        self.assertTrue(self.record(key, [4, 3, 4]).data["flagged"])  # safety question at or above 3
        self.assertIn("safety question", RiskFlag.objects.get().reason)
        self.assertEqual(self.record(key, [5, 0, 0]).status_code, 400)  # 5 isn't on the scale

        data = self.client.get(f"/api/practice/clients/{self.client_record.pk}/screenings/").data
        trend = next(t for t in data["trends"] if t["key"] == key)
        self.assertEqual((trend["instrument"], trend["latest_total"], trend["change"]), ("Weekly sleep check-in", 11, 4))
        self.assertEqual(data["screenings"][0]["instrument_name"], "Weekly sleep check-in")

    def test_questions_lock_once_used_and_archiving_keeps_history(self):
        created = self.create().data
        url = f"/api/practice/screening-templates/{created['id']}/"
        self.record(created["key"], [1, 1, 1])
        self.assertEqual(self.client.patch(url, {"items": ["New question"]}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"name": "Sleep check-in"}, format="json").data["name"], "Sleep check-in")

        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertTrue(ScreeningTemplate.objects.get(pk=created["id"]).archived)
        keys = [i["key"] for i in self.client.get("/api/screenings/instruments/").data]
        self.assertNotIn(created["key"], keys)
        self.assertEqual(self.record(created["key"], [1, 1, 1]).status_code, 400)  # can't record on an archived one
        history = self.client.get(f"/api/practice/clients/{self.client_record.pk}/screenings/").data["screenings"]
        self.assertEqual(history[0]["instrument_name"], "Sleep check-in")

    def test_templates_stay_within_their_practice(self):
        key = self.create().data["key"]
        other = self.make_therapist("drkim", "drkim@example.com")
        other_client, _ = self.link(other, self.make_user("bob", "bob@example.com"))
        self.login(other)
        self.assertNotIn(key, [i["key"] for i in self.client.get("/api/screenings/instruments/").data])
        res = self.client.post(f"/api/practice/clients/{other_client.pk}/screenings/",
                               {"instrument": key, "responses": [1, 1, 1]}, format="json")
        self.assertEqual(res.status_code, 400)
        template_id = key[1:]
        self.assertEqual(self.client.patch(f"/api/practice/screening-templates/{template_id}/", {"name": "x"},
                                           format="json").status_code, 404)

    def test_a_practice_with_template_results_can_be_deleted(self):
        key = self.create().data["key"]
        self.record(key, [1, 1, 1])
        self.client_record.practice.delete()  # e.g. account deletion; must not be blocked by template results
        self.assertFalse(ScreeningTemplate.objects.exists())
