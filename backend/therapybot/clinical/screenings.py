"""Recording screenings: score in code, flag safety items for the therapist, audit, and summarize trends."""

from django.db import transaction
from django.utils import timezone

from therapybot import audit
from therapybot.clinical.instruments import INSTRUMENTS, get_instrument
from therapybot.models import Client, RiskFlag, Screening

SAFETY_MESSAGE = (
    "Thank you for answering honestly. You mentioned thoughts of being better off dead or of hurting yourself. "
    "Your therapist will see this, but they may not see it right away. If you're thinking about harming "
    "yourself now, call or text 988 (US) or call 911."
)


def record_screening(*, client: Client, instrument_key: str, responses: list, administered_on=None,
                     source: str, entered_by, request=None) -> tuple[Screening, RiskFlag | None]:
    """
    Score and save one screening: a standard instrument or one of the client's practice's templates.
    Raises ValueError for an unknown or archived instrument, or invalid answers.
    """
    instrument = get_instrument(instrument_key, client.practice, include_archived=False)
    if instrument is None:
        raise ValueError("Unknown instrument")
    total, severity = instrument.score(list(responses))
    with transaction.atomic():
        screening = Screening.objects.create(
            client=client, instrument=instrument.key, responses=list(responses), total=total, severity=severity,
            template_id=int(instrument.key[1:]) if instrument.custom else None,
            administered_on=administered_on or timezone.localdate(), source=source, entered_by=entered_by,
        )
        flag = None
        if instrument.flags_risk(list(responses)):
            # Standard instruments name what the item is; a template's safety question is the therapist's own
            what = "thoughts of death or self-harm" if not instrument.custom else "safety question"
            top = max(o["value"] for o in instrument.options)
            flag = RiskFlag.objects.create(
                client=client, screening=screening, source_type=RiskFlag.SourceType.SCREENING,
                level=RiskFlag.Level.ELEVATED,
                reason=f"{instrument.name} item {instrument.risk_item + 1} ({what}) "
                       f"answered {responses[instrument.risk_item]} of {top}"[:200],
            )
    if flag is not None:
        from therapybot.between_sessions import notify_therapists

        notify_therapists(flag)
    audit.record(entered_by, "screening.record", request=request, client=client, obj=screening,
                 instrument=instrument.key, source=source, flagged=flag is not None)
    return screening, flag


def screening_trends(client: Client) -> list[dict]:
    """Latest score per instrument and the change since the previous one, for facts and the UI."""
    trends = []
    used = list(Screening.objects.filter(client=client).order_by().values_list("instrument", flat=True).distinct())
    keys = [k for k in INSTRUMENTS if k in used] + sorted(k for k in used if k not in INSTRUMENTS)
    for key in keys:
        instrument = get_instrument(key, client.practice)
        if instrument is None:
            continue
        recent = list(Screening.objects.filter(client=client, instrument=key)[:2])
        latest = recent[0]
        previous = recent[1] if len(recent) > 1 else None
        trends.append({
            "key": key,
            "instrument": instrument.name,
            "latest_total": latest.total,
            "latest_severity": latest.severity,
            "latest_date": latest.administered_on.isoformat(),
            "previous_total": previous.total if previous else None,
            "previous_date": previous.administered_on.isoformat() if previous else None,
            "change": latest.total - previous.total if previous else None,
            "max_total": instrument.max_total,
        })
    return trends
