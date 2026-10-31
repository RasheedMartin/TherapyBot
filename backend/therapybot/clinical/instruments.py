"""
Standardized screening instruments. PHQ-9 and GAD-7 were developed by Drs. Spitzer, Williams, Kroenke and
colleagues with an educational grant from Pfizer; no permission is required to reproduce, translate,
display or distribute them. Scoring is done here in code, never by a model.
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
    bands: tuple[tuple[int, str], ...]  # (minimum total, severity), ascending
    risk_item: int | None = None  # index of an item where any positive answer needs clinical follow-up

    @property
    def max_total(self) -> int:
        return 3 * len(self.items)

    def score(self, responses: list[int]) -> tuple[int, str]:
        if len(responses) != len(self.items):
            raise ValueError(f"{self.name} has {len(self.items)} items; got {len(responses)} answers")
        if any(not isinstance(r, int) or isinstance(r, bool) or not 0 <= r <= 3 for r in responses):
            raise ValueError("Each answer must be 0, 1, 2 or 3")
        total = sum(responses)
        severity = next(label for minimum, label in reversed(self.bands) if total >= minimum)
        return total, severity

    def as_dict(self) -> dict:
        return {"key": self.key, "name": self.name, "prompt": self.prompt, "items": list(self.items),
                "options": OPTIONS, "max_total": self.max_total}


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
