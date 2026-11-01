"""Email goes through Resend's HTTP API (Railway blocks SMTP on Hobby)."""

from unittest import mock

from django.core.mail import EmailMultiAlternatives, send_mail
from django.test import SimpleTestCase, override_settings


@override_settings(EMAIL_BACKEND="therapybot.email_backend.ResendBackend", RESEND_API_KEY="re_test",
                   DEFAULT_FROM_EMAIL="TherapyBot <no-reply@therapybot.app>")
class ResendBackendTests(SimpleTestCase):
    @mock.patch("therapybot.email_backend.requests.post")
    def test_sends_text_html_and_headers_with_a_timeout(self, post):
        post.return_value.status_code = 200
        message = EmailMultiAlternatives("Hi", "plain body", to=["a@example.com"],
                                         headers={"List-Unsubscribe": "<https://x/u>"})
        message.attach_alternative("<p>html</p>", "text/html")
        self.assertEqual(message.send(), 1)
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"], {
            "from": "TherapyBot <no-reply@therapybot.app>", "to": ["a@example.com"], "subject": "Hi",
            "text": "plain body", "html": "<p>html</p>", "headers": {"List-Unsubscribe": "<https://x/u>"},
        })
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test")
        self.assertEqual(kwargs["timeout"], 10)

    @mock.patch("therapybot.email_backend.requests.post")
    def test_errors_raise_unless_failing_silently(self, post):
        post.return_value.status_code = 403
        post.return_value.text = '{"message": "The therapybot.app domain is not verified"}'
        with self.assertRaisesMessage(RuntimeError, "not verified"):
            send_mail("s", "b", None, ["a@example.com"])
        self.assertEqual(send_mail("s", "b", None, ["a@example.com"], fail_silently=True), 0)
