"""Phase 1: therapist accounts, client records, consented care relationships, and access control."""

import logging
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail

from therapybot.models import AuditEvent, CareRelationship, Client, Practice, Profile
from therapybot.tests.helpers import CONSENT, STRONG_PASSWORD, APITestCase

THERAPIST_SIGNUP = {
    "username": "drlee", "email": "drlee@example.com", "password": STRONG_PASSWORD,
    "first_name": "Dana", "last_name": "Lee", "npi": "1801415708", **CONSENT,
}


def invite_token_from_outbox():
    return re.search(r"/care-team/invite\?t=(\S+)", mail.outbox[-1].body).group(1)


class TherapistRegistrationTests(APITestCase):
    @mock.patch("therapybot.providers.verify_therapist_npi", return_value=("verified", {"credential": "PhD"}))
    def test_verified_npi_creates_therapist_and_practice(self, verify):
        res = self.client.post("/api/therapists/register/", {**THERAPIST_SIGNUP, "practice_name": "Calm Harbor"},
                               format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["role"], res.data["npi_status"]), ("therapist", "verified"))
        user = User.objects.get(username="drlee")
        self.assertEqual(user.practice_memberships.get().practice.name, "Calm Harbor")
        self.assertIsNotNone(user.profile.npi_verified_at)
        verify.assert_called_once_with("1801415708", "Dana", "Lee")
        self.assertTrue(AuditEvent.objects.filter(action="therapist.register").exists())

    @mock.patch("therapybot.providers.verify_therapist_npi", return_value=("needs_review", {"reason": "name_mismatch"}))
    def test_unconfirmed_npi_goes_to_review_and_cannot_see_clients(self, _):
        self.client.post("/api/therapists/register/", THERAPIST_SIGNUP, format="json")
        user = User.objects.get(username="drlee")
        self.assertEqual(user.profile.npi_status, "needs_review")
        user.profile.email_verified_at = user.date_joined
        user.profile.save()
        self.login(user)
        self.assertEqual(self.client.get("/api/practice/clients/").status_code, 403)

    def test_rejects_invalid_and_duplicate_npi(self):
        res = self.client.post("/api/therapists/register/", {**THERAPIST_SIGNUP, "npi": "1801415709"}, format="json")
        self.assertIn("npi", res.data)  # check digit wrong
        self.make_therapist(username="other", email="other@example.com")  # already holds 1801415708
        res = self.client.post("/api/therapists/register/", THERAPIST_SIGNUP, format="json")
        self.assertIn("npi", res.data)

    def test_npi_check_digit(self):
        from therapybot.providers import npi_checksum_ok

        self.assertTrue(npi_checksum_ok("1801415708"))
        self.assertFalse(npi_checksum_ok("1234567890"))
        self.assertFalse(npi_checksum_ok("18014157"))


class RoleGatingTests(APITestCase):
    def test_clients_cannot_use_practice_endpoints(self):
        self.login(self.make_user())
        self.assertEqual(self.client.get("/api/practice/clients/").status_code, 403)
        self.assertEqual(self.client.post("/api/practice/clients/", {"display_name": "X", "email": "x@example.com"}).status_code, 403)


class InviteFlowTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.login(self.therapist)
        res = self.client.post("/api/practice/clients/", {"display_name": "Sam Rivera", "email": "Sam@Example.com"},
                               format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.client_id = res.data["id"]
        self.token = invite_token_from_outbox()

    def test_invite_preview_accept_and_roster(self):
        self.assertEqual(mail.outbox[-1].to, ["sam@example.com"])
        self.client.force_authenticate(None)
        preview = self.client.get(f"/api/care-team/invite/?t={self.token}").data
        self.assertIn("Dana Lee", preview["therapist_name"])
        self.assertIn("not live monitoring", preview["always_shared"])
        self.assertFalse(preview["defaults"]["share_raw_chat"])

        sam = self.make_user("sam", "sam@example.com")
        self.login(sam)
        res = self.client.post("/api/care-team/accept/", {"t": self.token, "share_chat_summaries": False}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        rel = CareRelationship.objects.get()
        self.assertEqual((rel.status, rel.client.user, rel.share_chat_summaries, rel.share_checkins),
                         ("active", sam, False, True))
        self.assertIsNotNone(rel.consented_at)

        self.assertEqual(len(self.client.get("/api/care-team/").data), 1)
        self.login(self.therapist)
        roster = self.client.get("/api/practice/clients/").data
        self.assertEqual([(c["display_name"], c["has_account"], c["relationship"]["status"]) for c in roster],
                         [("Sam Rivera", True, "active")])

    def test_invite_link_is_single_use(self):
        sam = self.make_user("sam", "sam@example.com")
        self.login(sam)
        self.assertEqual(self.client.post("/api/care-team/accept/", {"t": self.token}).status_code, 200)
        self.assertEqual(self.client.post("/api/care-team/accept/", {"t": self.token}).status_code, 400)

    def test_cannot_accept_from_a_different_account(self):
        mallory = self.make_user("mallory", "mallory@example.com")
        self.login(mallory)
        res = self.client.post("/api/care-team/accept/", {"t": self.token})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(CareRelationship.objects.get().status, "invited")
        self.assertIsNone(Client.objects.get().user)
        self.assertTrue(AuditEvent.objects.filter(action="relationship.accept", outcome="denied").exists())

    def test_tampered_token_rejected(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f"/api/care-team/invite/?t={self.token}x").status_code, 400)

    def test_duplicate_invite_rejected(self):
        res = self.client.post("/api/practice/clients/", {"display_name": "Sam", "email": "sam@example.com"},
                               format="json")
        self.assertEqual(res.status_code, 400)


class IsolationTests(APITestCase):
    """A therapist can only ever reach clients who are currently in their care."""

    def setUp(self):
        super().setUp()
        self.lee = self.make_therapist()
        self.kim = self.make_therapist("drkim", "drkim@example.com")
        self.sam = self.make_user("sam", "sam@example.com")
        self.sams_record, self.rel = self.link(self.lee, self.sam)

    def test_other_therapist_gets_404_and_is_audited(self):
        self.login(self.kim)
        self.assertEqual(self.client.get(f"/api/practice/clients/{self.sams_record.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/practice/clients/").data, [])
        self.assertEqual(self.client.post(f"/api/practice/clients/{self.sams_record.pk}/end/").status_code, 404)
        denied = AuditEvent.objects.get(action="client.view", outcome="denied")
        self.assertEqual(denied.actor, self.kim)

    def test_nonexistent_and_forbidden_clients_look_the_same(self):
        self.login(self.kim)
        missing = self.client.get("/api/practice/clients/999999/")
        forbidden = self.client.get(f"/api/practice/clients/{self.sams_record.pk}/")
        self.assertEqual((missing.status_code, missing.data), (forbidden.status_code, forbidden.data))

    def test_access_ends_when_client_leaves(self):
        self.login(self.lee)
        self.assertEqual(self.client.get(f"/api/practice/clients/{self.sams_record.pk}/").status_code, 200)
        self.login(self.sam)
        self.assertEqual(self.client.post(f"/api/care-team/{self.rel.pk}/leave/").status_code, 204)
        self.login(self.lee)
        self.assertEqual(self.client.get(f"/api/practice/clients/{self.sams_record.pk}/").status_code, 404)

    def test_only_the_client_controls_sharing(self):
        self.login(self.sam)
        res = self.client.patch(f"/api/care-team/{self.rel.pk}/", {"share_raw_chat": True}, format="json")
        self.assertTrue(res.data["share_raw_chat"])
        for intruder in (self.lee, self.make_user("eve", "eve@example.com")):
            self.login(intruder)
            res = self.client.patch(f"/api/care-team/{self.rel.pk}/", {"share_raw_chat": False}, format="json")
            self.assertEqual(res.status_code, 404)
        self.rel.refresh_from_db()
        self.assertTrue(self.rel.share_raw_chat)

    def test_client_can_have_several_therapists(self):
        self.link(self.kim, self.sam)
        self.login(self.sam)
        self.assertEqual(len(self.client.get("/api/care-team/").data), 2)
        for therapist in (self.lee, self.kim):
            self.login(therapist)
            self.assertEqual(len(self.client.get("/api/practice/clients/").data), 1)


class SamePracticeRecordTests(APITestCase):
    def test_accepting_reuses_the_practices_existing_record(self):
        practice = Practice.objects.create(name="Shared practice")
        lee = self.make_therapist(practice=practice)
        kim = self.make_therapist("drkim", "drkim@example.com", practice=practice)
        sam = self.make_user("sam", "sam@example.com")
        existing, _ = self.link(lee, sam)
        existing.email = "sam.old@example.com"  # the practice has an older address on file
        existing.save()

        self.login(kim)
        self.client.post("/api/practice/clients/", {"display_name": "Sam R", "email": "sam@example.com"}, format="json")
        self.login(sam)
        res = self.client.post("/api/care-team/accept/", {"t": invite_token_from_outbox()})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Client.objects.filter(practice=practice).count(), 1)  # placeholder merged away
        self.assertEqual(set(existing.relationships.values_list("therapist__username", flat=True)), {"drlee", "drkim"})
        self.assertEqual(CareRelationship.objects.get(therapist=kim).status, "active")


class AuditAndLoggingTests(APITestCase):
    def test_audit_log_is_append_only(self):
        event = AuditEvent.objects.create(action="test")
        event.action = "edited"
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            event.delete()

    def test_audit_metadata_refuses_content(self):
        from therapybot import audit

        with self.assertRaises(ValueError):
            audit.record(None, "client.view", note="Pt reports...")

    def test_logs_redact_emails_and_phone_numbers(self):
        from therapybot.logging_filters import RedactPII

        record = logging.LogRecord("x", logging.ERROR, "", 0, "Invite to %s failed (call %s)",
                                   ("sam@example.com", "(212) 555-1234"), None)
        RedactPII().filter(record)
        self.assertEqual(record.getMessage(), "Invite to [email] failed (call [phone])")

    def test_config_exposes_phi_switch(self):
        self.assertFalse(self.client.get("/api/config/").data["phi_allowed"])
        self.assertEqual(Profile._meta.get_field("role").default, "client")
