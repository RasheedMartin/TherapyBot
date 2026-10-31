"""Phase 4: PHQ-9 / GAD-7 scoring, risk flags from safety items, self-report, and trends."""

from datetime import timedelta

from django.db import connection
from django.utils import timezone

from therapybot.clinical.facts import client_facts, render_facts
from therapybot.clinical.instruments import GAD7, PHQ9
from therapybot.models import RiskFlag, Screening
from therapybot.tests.helpers import APITestCase


def answers(total, n, risk_item=None, risk_value=0):
    """n item scores summing to `total`, optionally with a set value at the risk item."""
    scores = [0] * n
    if risk_item is not None:
        scores[risk_item] = risk_value
    remaining = total - sum(scores)
    for i in range(n):
        if i == risk_item:
            continue
        add = min(3, remaining)
        scores[i], remaining = add, remaining - add
    assert remaining == 0
    return scores


class ScoringTests(APITestCase):
    def test_severity_bands_at_every_boundary(self):
        for total, band in [(0, "minimal"), (4, "minimal"), (5, "mild"), (9, "mild"), (10, "moderate"),
                            (14, "moderate"), (15, "moderately severe"), (19, "moderately severe"),
                            (20, "severe"), (27, "severe")]:
            self.assertEqual(PHQ9.score(answers(total, 9)), (total, band), total)
        for total, band in [(4, "minimal"), (5, "mild"), (10, "moderate"), (14, "moderate"), (15, "severe"),
                            (21, "severe")]:
            self.assertEqual(GAD7.score(answers(total, 7)), (total, band), total)

    def test_invalid_answers_are_rejected(self):
        for bad in ([1] * 8, [1] * 10, [4] + [0] * 8, [-1] + [0] * 8, [True] + [0] * 8, ["2"] + [0] * 8):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                PHQ9.score(bad)


class ScreeningFlowTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.lee = self.make_therapist()
        self.sam = self.make_user("sam", "sam@example.com")
        self.record, self.rel = self.link(self.lee, self.sam)
        self.base = f"/api/practice/clients/{self.record.pk}"

    def test_positive_item_9_flags_the_therapist(self):
        self.login(self.lee)
        res = self.client.post(f"{self.base}/screenings/", {"instrument": "phq9",
                               "responses": answers(12, 9, risk_item=8, risk_value=1)}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["total"], res.data["severity"], res.data["flagged"]), (12, "moderate", True))
        inbox = self.client.get("/api/practice/risk-flags/").data
        self.assertEqual(len(inbox), 1)
        self.assertIn("item 9", inbox[0]["reason"])

        kim = self.make_therapist("drkim", "drkim@example.com")
        self.login(kim)
        self.assertEqual(self.client.get("/api/practice/risk-flags/").data, [])
        self.assertEqual(self.client.post(f"/api/practice/risk-flags/{inbox[0]['id']}/acknowledge/").status_code, 404)

        self.login(self.lee)
        acked = self.client.post(f"/api/practice/risk-flags/{inbox[0]['id']}/acknowledge/").data
        self.assertIsNotNone(acked["acknowledged_at"])

    def test_negative_item_9_does_not_flag_even_when_severe(self):
        self.login(self.lee)
        res = self.client.post(f"{self.base}/screenings/", {"instrument": "phq9", "responses": answers(24, 9, 8, 0)},
                               format="json")
        self.assertFalse(res.data["flagged"])
        self.assertFalse(RiskFlag.objects.exists())

    def test_client_self_report_shows_support_immediately(self):
        self.login(self.sam)
        res = self.client.post("/api/screenings/mine/", {"client": self.record.pk, "instrument": "phq9",
                               "responses": answers(8, 9, risk_item=8, risk_value=2)}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["source"], "self_report")
        self.assertIn("988", res.data["support_message"])
        self.assertEqual(len(self.client.get("/api/screenings/mine/").data), 1)

    def test_clients_cannot_report_into_other_records_or_ended_care(self):
        riley = self.make_user("riley", "riley@example.com")
        riley_record, _ = self.link(self.lee, riley)
        self.login(self.sam)
        res = self.client.post("/api/screenings/mine/", {"client": riley_record.pk, "instrument": "gad7",
                               "responses": [0] * 7}, format="json")
        self.assertEqual(res.status_code, 404)
        self.rel.status = "ended"
        self.rel.save()
        res = self.client.post("/api/screenings/mine/", {"client": self.record.pk, "instrument": "gad7",
                               "responses": [0] * 7}, format="json")
        self.assertEqual(res.status_code, 404)
        self.assertFalse(Screening.objects.exists())

    def test_trends_feed_session_prep_facts(self):
        today = timezone.localdate()
        for days_ago, total in ((28, 14), (0, 9)):
            Screening.objects.create(client=self.record, instrument="gad7", responses=answers(total, 7),
                                     total=total, severity=GAD7.score(answers(total, 7))[1],
                                     administered_on=today - timedelta(days=days_ago), source="clinician")
        facts = client_facts(self.record, self.lee)
        gad = facts["screenings"][0]
        self.assertEqual((gad["latest_total"], gad["previous_total"], gad["change"]), (9, 14, -5))
        self.assertIn("GAD-7: 9/21 (mild)", render_facts(facts))
        self.assertIn("-5 since", render_facts(facts))

    def test_item_responses_are_encrypted_at_rest(self):
        self.login(self.lee)
        self.client.post(f"{self.base}/screenings/", {"instrument": "gad7", "responses": [1, 2, 3, 0, 1, 2, 3]},
                         format="json")
        with connection.cursor() as cursor:
            cursor.execute("select responses from therapybot_screening")
            self.assertTrue(cursor.fetchone()[0].startswith("enc:v1:"))

    def test_instrument_definitions(self):
        self.login(self.sam)
        defs = {d["key"]: d for d in self.client.get("/api/screenings/instruments/").data}
        self.assertEqual((len(defs["phq9"]["items"]), defs["phq9"]["max_total"]), (9, 27))
        self.assertEqual(len(defs["gad7"]["options"]), 4)
