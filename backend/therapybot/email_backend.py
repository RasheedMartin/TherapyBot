"""
Send email through Resend's HTTP API. Railway blocks outbound SMTP on its Hobby plan, so SMTP connections
hang until they time out; HTTPS isn't blocked. Supports what the app sends: plain text, an HTML
alternative, reply-to, cc/bcc and extra headers (List-Unsubscribe).
"""

import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT = 10


class ResendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            payload = {
                "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": list(message.to),
                "subject": message.subject,
                "text": message.body,
            }
            for content, mimetype in getattr(message, "alternatives", []):
                if mimetype == "text/html":
                    payload["html"] = content
            if message.cc:
                payload["cc"] = list(message.cc)
            if message.bcc:
                payload["bcc"] = list(message.bcc)
            if message.reply_to:
                payload["reply_to"] = list(message.reply_to)
            if message.extra_headers:
                payload["headers"] = dict(message.extra_headers)
            try:
                res = requests.post(
                    RESEND_URL, json=payload, timeout=TIMEOUT,
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                )
                if res.status_code >= 400:
                    # Resend's error body says why (e.g. the sending domain isn't verified); it has no message content
                    raise RuntimeError(f"Resend returned {res.status_code}: {res.text[:300]}")
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("Resend send failed")
                continue
            sent += 1
        return sent
