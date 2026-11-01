"""
Screening instruments: the standard PHQ-9 and GAD-7, plus templates therapists build for their practice
(models.ScreeningTemplate), which become Instruments too, so scoring, safety flags and trends work the
same way for all of them. PHQ-9 and GAD-7 were developed by Drs. Spitzer, Williams, Kroenke and colleagues
with an educational grant from Pfizer; no permission is required to reproduce, translate, display or
distribute them. Scoring is done here in code, never by a model.
"""

from dataclasses import dataclass

OPTIONS = [
    {"value": 0, "label": "Not at all"},
    {"value": 1, "label": "Several days"},
    {"value": 2, "label": "More than half the days"},
    {"value": 3, "label": "Nearly every day"},
]


@dataclass(frozen=True)
class Instrument:
    key: str
    name: str
    prompt: str
    items: tuple[str, ...]
    bands: tuple[tuple[int, str], ...]  # (minimum total, label), ascending; may be empty
    risk_item: int | None = None  # index of an item where an answer at or above risk_min needs follow-up
    options: tuple[dict, ...] = tuple(OPTIONS)  # [{"value", "label"}], ascending values
    risk_min: int = 1
    custom: bool = False  # a practice's own template rather than a standard instrument

    @property
    def max_total(self) -> int:
        return max(o["value"] for o in self.options) * len(self.items)

    def score(self, responses: list[int]) -> tuple[int, str]:
        if len(responses) != len(self.items):
            raise ValueError(f"{self.name} has {len(self.items)} items; got {len(responses)} answers")
        allowed = {o["value"] for o in self.options}
        if any(not isinstance(r, int) or isinstance(r, bool) or r not in allowed for r in responses):
            raise ValueError(f"Each answer must be one of {', '.join(str(v) for v in sorted(allowed))}")
        total = sum(responses)
        severity = next((label for minimum, label in reversed(self.bands) if total >= minimum), "")
        return total, severity

    def flags_risk(self, responses: list[int]) -> bool:
        return self.risk_item is not None and responses[self.risk_item] >= self.risk_min

    def as_dict(self) -> dict:
        return {"key": self.key, "name": self.name, "prompt": self.prompt, "items": list(self.items),
                "options": list(self.options), "max_total": self.max_total, "custom": self.custom,
                "bands": [{"min": m, "label": label} for m, label in self.bands], "risk_item": self.risk_item}


PHQ9 = Instrument(
    key="phq9",
    name="PHQ-9",
    prompt="Over the last 2 weeks, how often have you been bothered by any of the following problems?",
    items=(
        "Little interest or pleasure in doing things",
        "Feeling down, depressed, or hopeless",
        "Trouble falling or staying asleep, or sleeping too much",
        "Feeling tired or having little energy",
        "Poor appetite or overeating",
        "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
        "Trouble concentrating on things, such as reading the newspaper or watching television",
        "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so "
        "fidgety or restless that you have been moving around a lot more than usual",
        "Thoughts that you would be better off dead or of hurting yourself in some way",
    ),
    bands=((0, "minimal"), (5, "mild"), (10, "moderate"), (15, "moderately severe"), (20, "severe")),
    risk_item=8,
)

GAD7 = Instrument(
    key="gad7",
    name="GAD-7",
    prompt="Over the last 2 weeks, how often have you been bothered by the following problems?",
    items=(
        "Feeling nervous, anxious, or on edge",
        "Not being able to stop or control worrying",
        "Worrying too much about different things",
        "Trouble relaxing",
        "Being so restless that it is hard to sit still",
        "Becoming easily annoyed or irritable",
        "Feeling afraid as if something awful might happen",
    ),
    bands=((0, "minimal"), (5, "mild"), (10, "moderate"), (15, "severe")),
)

INSTRUMENTS = {i.key: i for i in (PHQ9, GAD7)}


def template_key(template_id: int) -> str:
    return f"t{template_id}"


def get_instrument(key: str, practice=None, include_archived: bool = True) -> Instrument | None:
    """A standard instrument by key, or one of `practice`'s templates ("t12"). None if unknown or not theirs."""
    if key in INSTRUMENTS:
        return INSTRUMENTS[key]
    if practice is None or not key.startswith("t") or not key[1:].isdigit():
        return None
    from therapybot.models import ScreeningTemplate

    templates = ScreeningTemplate.objects.filter(pk=int(key[1:]), practice=practice)
    if not include_archived:
        templates = templates.filter(archived=False)
    template = templates.first()
    return template.as_instrument() if template else None
