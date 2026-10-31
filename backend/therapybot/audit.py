"""Write the access audit log. Metadata must be identifiers and counts only, never clinical content."""

from therapybot.models import AuditEvent

_FORBIDDEN_KEYS = {"text", "content", "body", "note", "notes", "transcript", "message", "summary", "email", "name"}


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


def record(actor, action: str, *, request=None, client=None, practice=None, obj=None, denied=False, **metadata):
    """Append one audit event. Raises if metadata looks like it carries PHI."""
    leaked = _FORBIDDEN_KEYS & {key.lower() for key in metadata}
    if leaked:
        raise ValueError(f"Audit metadata must not contain {sorted(leaked)}")
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        outcome=AuditEvent.Outcome.DENIED if denied else AuditEvent.Outcome.ALLOWED,
        practice=practice or (client.practice if client else None),
        client=client,
        object_type=type(obj).__name__ if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
        metadata=metadata,
        ip_address=_client_ip(request),
    )
