"""The admin is off unless ADMIN_ENABLED; NPI review works without it."""

import importlib
from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.urls import Resolver404, clear_url_caches, resolve

import djangoProject.urls
from therapybot.models import AuditEvent, Profile
from therapybot.tests.helpers import APITestCase


class AdminToggleTests(APITestCase):
    def _reload_urls(self):
        clear_url_caches()
        importlib.reload(djangoProject.urls)

    def tearDown(self):
        self._reload_urls()  # back to the test settings' URLconf
        super().tearDown()

    def test_admin_url_exists_only_when_enabled(self):
        with override_settings(ADMIN_ENABLED=False):
            self._reload_urls()
            with self.assertRaises(Resolver404):
                resolve("/admin/")
        with override_settings(ADMIN_ENABLED=True):
            self._reload_urls()
            self.assertEqual(resolve("/admin/").app_name, "admin")


class ApproveNpiCommandTests(APITestCase):
    def test_approve_reject_and_list_pending(self):
        therapist = self.make_therapist(npi_status="needs_review")
        out = StringIO()
        call_command("approve_npi", "--pending", stdout=out)
        self.assertIn("drlee", out.getvalue())

        call_command("approve_npi", "drlee", stdout=StringIO())
        therapist.profile.refresh_from_db()
        self.assertEqual(therapist.profile.npi_status, Profile.NpiStatus.VERIFIED)
        self.assertIsNotNone(therapist.profile.npi_verified_at)

        call_command("approve_npi", "drlee", "--reject", stdout=StringIO())
        therapist.profile.refresh_from_db()
        self.assertEqual((therapist.profile.npi_status, therapist.profile.npi_verified_at), ("rejected", None))
        self.assertEqual(AuditEvent.objects.filter(action="therapist.npi_review").count(), 2)

    def test_only_therapist_accounts(self):
        self.make_user()
        from django.core.management.base import CommandError

        with self.assertRaisesMessage(CommandError, "No therapist account"):
            call_command("approve_npi", "alice", stdout=StringIO())
