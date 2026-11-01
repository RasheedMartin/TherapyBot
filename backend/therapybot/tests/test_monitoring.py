"""Sentry events carry the error and route, never what people wrote or who they are."""

from django.test import SimpleTestCase

from therapybot.monitoring import scrub_event


class ScrubEventTests(SimpleTestCase):
    def test_removes_user_content_identity_and_tokens(self):
        event = {
            "request": {
                "url": "https://api.example/api/care-team/invite/?t=SECRET-TOKEN",
                "query_string": "t=SECRET-TOKEN",
                "data": {"content": "I had a panic attack"},
                "cookies": {"sessionid": "x"},
                "headers": {"Authorization": "Bearer abc", "Content-Type": "application/json"},
            },
            "user": {"id": 7, "email": "client@example.com"},
            "exception": {"values": [{
                "value": "bad value for alice@example.com: enc:v1:gAAAAB123abc t=SECRET-TOKEN",
                "stacktrace": {"frames": [{"function": "send_message", "vars": {"content": "panic attack"}}]},
            }]},
            "breadcrumbs": {"values": [
                {"message": "GET /api/calendar/feed?token=abc123", "data": {"url": "https://x/y?t=1", "params": ["panic"]}},
            ]},
        }
        out = scrub_event(event)
        text = repr(out)
        for leaked in ("panic", "SECRET-TOKEN", "alice@example.com", "client@example.com", "Bearer", "gAAAAB123abc",
                       "abc123", "sessionid"):
            self.assertNotIn(leaked, text)
        self.assertEqual(out["request"]["url"], "https://api.example/api/care-team/invite/")
        self.assertEqual(out["request"]["headers"], {"Content-Type": "application/json"})
        self.assertNotIn("user", out)
        self.assertEqual(out["exception"]["values"][0]["stacktrace"]["frames"][0], {"function": "send_message"})
        self.assertIn("[email]", out["exception"]["values"][0]["value"])
