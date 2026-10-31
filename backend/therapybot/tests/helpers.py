"""Shared test fixtures. All data here is synthetic."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from therapybot.models import CareRelationship, Client, Practice, PracticeMembership, Profile

STRONG_PASSWORD = "calm-River-42-lantern"
CONSENT = {"confirm_age": True, "accept_terms": True}


class APITestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def make_user(self, username="alice", email="alice@example.com", verified=True):
        user = User.objects.create_user(username=username, email=email, password=STRONG_PASSWORD)
        Profile.objects.create(user=user, email_verified_at=timezone.now() if verified else None)
        return user

    def make_therapist(self, username="drlee", email="drlee@example.com", npi_status="verified", practice=None):
        user = User.objects.create_user(username=username, email=email, password=STRONG_PASSWORD,
                                        first_name="Dana", last_name="Lee")
        Profile.objects.create(user=user, role="therapist", npi="1801415708", npi_status=npi_status,
                               email_verified_at=timezone.now())
        practice = practice or Practice.objects.create(name=f"{username} practice")
        PracticeMembership.objects.create(practice=practice, user=user, role="owner")
        return user

    def link(self, therapist, client_user, status="active", **scopes):
        """An existing care relationship between a therapist and a client account (synthetic)."""
        practice = therapist.practice_memberships.first().practice
        client = Client.objects.create(practice=practice, display_name=client_user.username.title(),
                                       email=client_user.email, user=client_user, created_by=therapist)
        rel = CareRelationship.objects.create(client=client, therapist=therapist, status=status,
                                              consented_at=timezone.now() if status == "active" else None, **scopes)
        return client, rel

    def login(self, user):
        self.client.force_authenticate(user)
