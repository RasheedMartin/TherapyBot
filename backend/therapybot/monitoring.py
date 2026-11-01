"""
Error monitoring with Sentry, without sending what people write. Events carry the error, stack trace and
route only: no request bodies, cookies, auth headers, query strings (invite and calendar tokens), user
identity, or local variables (which can hold chat or note text). Off unless SENTRY_DSN is set.
"""

import os
import re

SENSITIVE_HEADERS = {"authorization", "cookie", "x-csrftoken", "x-forwarded-for", "x-real-ip"}
# Values that look like secrets or identifiers even inside an exception message
_REDACTIONS = [
    (re.compile(r"enc:v1:[A-Za-z0-9_\-=]+"), "enc:v1:[redacted]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b(t|token|uid)=[^&\s]+"), r"\1=[redacted]"),
]


def _redact(text):
    if not isinstance(text, str):
        return text
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _strip_query(url):
    return url.split("?", 1)[0] if isinstance(url, str) else url


def scrub_event(event, hint=None):
    """before_send: keep what's needed to debug, drop anything a person typed or that identifies them."""
    request = event.get("request") or {}
    for key in ("data", "cookies", "query_string", "env"):
        request.pop(key, None)
    if "url" in request:
        request["url"] = _strip_query(request["url"])
    if isinstance(request.get("headers"), dict):
        request["headers"] = {k: v for k, v in request["headers"].items() if k.lower() not in SENSITIVE_HEADERS}
    if request:
        event["request"] = request
    event.pop("user", None)

    for exception in (event.get("exception") or {}).get("values", []):
        exception["value"] = _redact(exception.get("value"))
        for frame in (exception.get("stacktrace") or {}).get("frames", []):
            frame.pop("vars", None)
    if isinstance(event.get("logentry"), dict):
        event["logentry"]["message"] = _redact(event["logentry"].get("message"))
        event["logentry"].pop("params", None)
    for crumb in (event.get("breadcrumbs") or {}).get("values", []):
        crumb["message"] = _redact(crumb.get("message"))
        data = crumb.get("data") or {}
        if "url" in data:
            data["url"] = _strip_query(data["url"])
        data.pop("params", None)  # SQL parameters
    return event


def init_sentry():
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        environment=os.getenv("RAILWAY_ENVIRONMENT_NAME", "development"),
        release=os.getenv("RAILWAY_GIT_COMMIT_SHA") or None,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
        before_send=scrub_event,
        before_send_transaction=scrub_event,
    )
