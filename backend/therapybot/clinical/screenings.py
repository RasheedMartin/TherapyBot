"""Recording screenings: score in code, flag safety items for the therapist, audit, and summarize trends."""

from django.db import transaction
from django.utils import timezone

from therapybot import audit
from therapybot.clinical.instruments import INSTRUMENTS
from therapybot.models import Client, RiskFlag, Screening

SAFETY_MESSAGE = (
    "Thank you for answering honestly. You mentioned thoughts of being better off dead or of hurting yourself. "
    "Your therapist will see this, but they may not see it right away. If you're thinking about harming "
    "yourself now, call or text 988 (US) or call 911."
)


def record_screening(*, client: Client, instrument_key: str, responses: list, administered_on=None,
                     source: str, entered_by, request=None) -> tuple[Screening, RiskFlag | None]:
    """Score and save one screening. Raises ValueError for an unknown instrument or invalid answers."""
    instrument = INSTRUMENTS.get(instrument_key)
    if instrument is None:
        raise ValueError("Unknown instrument")
    total, severity = instrument.score(list(responses))
    with transaction.atomic():
        screening = Screening.objects.create(
            client=client, instrument=instrument.key, responses=list(responses), total=total, severity=severity,
            administered_on=administered_on or timezone.localdate(), source=source, entered_by=entered_by,
        )
        flag = None
        if instrument.risk_item is not None and responses[instrument.risk_item] > 0:
            flag = RiskFlag.objects.create(
                client=client, screening=screening, source_type=RiskFlag.SourceType.SCREENING,
                level=RiskFlag.Level.ELEVATED,
                reason=f"{instrument.name} item {instrument.risk_item + 1} (thoughts of death or self-harm) "
                       f"answered {responses[instrument.risk_item]} of 3",
            )
    audit.record(entered_by, "screening.record", request=request, client=client, obj=screening,
                 instrument=instrument.key, source=source, flagged=flag is not None)
    return screening, flag


def screening_trends(client: Client) -> list[dict]:
    """Latest score per instrument and the change since the previous one, for facts and the UI."""
    trends = []
    for key, instrument in INSTRUMENTS.items():
        recent = list(Screening.objects.filter(client=client, instrument=key)[:2])
        if not recent:
            continue
        latest = recent[0]
        previous = recent[1] if len(recent) > 1 else None
        trends.append({
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
