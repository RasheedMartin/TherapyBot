"""
Citations for therapist-facing AI output. The model sees record excerpts labeled [S1]…[Sn] and must cite
them; the server then keeps only citations to labels it actually supplied, and drops claims that have
none. A made-up session can't reach the UI because it has no label to point to.
"""

import re
from dataclasses import dataclass

from therapybot.models import ClinicalDocument
from therapybot.rag import RetrievedChunk

SNIPPET_CHARS = 220
DOC_TYPE_LABELS = {**dict(ClinicalDocument.DocType.choices),
                   "chat_summary": "Companion chat summary (shared by the client)"}
MARKER_RE = re.compile(r"\[S(\d+)\]")
_BRACKETS = str.maketrans({"【": "[", "】": "]", "［": "[", "］": "]", "〔": "[", "〕": "]"})
# Models use narrow/no-break spaces (e.g. "GAD‑7\u202f9"); some fonts render them with ~no width
_ODD_SPACES = str.maketrans({"\u202f": " ", "\u00a0": " ", "\u2009": " ", "\u2007": " "})
# ...and zero-width characters, even inside markers ("[\u200bS1]")
_INVISIBLE = str.maketrans({c: None for c in "\u200b\u200c\u200d\u2060\ufeff"})
# Statements drawn from the FACTS block (computed from the database) cite it as [FACTS]
FACTS = "FACTS"
FACTS_RE = re.compile(r"\[\s*FACTS\s*\]", re.IGNORECASE)
_GROUPED_RE = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)+)\s*\]")


def normalize_markers(text: str) -> str:
    """Models sometimes write 【S1】 or [S1, S2]; rewrite those as [S1] / [S1][S2] before validating."""
    text = (text or "").translate(_BRACKETS).translate(_ODD_SPACES).translate(_INVISIBLE)
    text = _GROUPED_RE.sub(lambda m: "".join(f"[{p.strip()}]" for p in re.split(r"[,;]", m.group(1))), text)
    return re.sub(r"\[\s*S\s*(\d+)\s*\]", r"[S\1]", text)


@dataclass(frozen=True)
class Source:
    label: str
    chunk: RetrievedChunk

    def as_dict(self) -> dict:
        text = " ".join(self.chunk.text.split())
        # Chat summaries have no document to open, so the citation carries all of it
        limit = len(text) if self.chunk.doc_type == "chat_summary" else SNIPPET_CHARS
        return {
            "label": self.label,
            "document_id": self.chunk.document_id,
            "session_id": self.chunk.session_id,
            "session_date": self.chunk.session_date,
            "doc_type": self.chunk.doc_type,
            "snippet": text[:limit] + ("…" if len(text) > limit else ""),
        }


def label_chunks(chunks: list[RetrievedChunk]) -> list[Source]:
    return [Source(f"S{i}", chunk) for i, chunk in enumerate(chunks, start=1)]


def render_sources(sources: list[Source]) -> str:
    """The SOURCES block given to the model."""
    if not sources:
        return "(The record has no documents yet.)"
    blocks = []
    for s in sources:
        kind = DOC_TYPE_LABELS.get(s.chunk.doc_type, "Document")
        blocks.append(f"[{s.label}] {kind}, {s.chunk.session_date or 'undated'}\n{s.chunk.text.strip()}")
    return "\n\n".join(blocks)


def _valid_labels(raw, by_label: dict) -> list[str]:
    labels = []
    for item in raw if isinstance(raw, list) else []:
        label = str(item).translate(_BRACKETS).translate(_INVISIBLE).strip().strip("[]").replace(" ", "").upper()
        if (label in by_label or label == FACTS) and label not in labels:
            labels.append(label)
    return labels


def validate_items(items, sources: list[Source]) -> tuple[list[dict], int]:
    """
    Keep {"text", "sources"} items that cite at least one real source or the FACTS block. Returns
    (kept, dropped_count).
    """
    by_label = {s.label: s for s in sources}
    kept, dropped = [], 0
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        labels = _valid_labels(item.get("sources"), by_label)
        if not labels:
            dropped += 1
            continue
        kept.append({"text": str(item["text"]).translate(_ODD_SPACES).strip(), "sources": labels})
    return kept, dropped


def validate_text(text: str, sources: list[Source]) -> tuple[str, list[str]]:
    """
    Remove [S#] markers that don't match a supplied source, and [FACTS] markers (FACTS is shown separately).
    Returns (clean text, labels actually cited), with "FACTS" among the labels if the text relied on it.
    """
    by_label = {s.label: s for s in sources}
    cited = []

    def keep(match):
        label = f"S{match.group(1)}"
        if label in by_label:
            if label not in cited:
                cited.append(label)
            return match.group(0)
        return ""

    text = normalize_markers(text)
    if FACTS_RE.search(text):
        cited.append(FACTS)
        text = FACTS_RE.sub("", text)
    clean = MARKER_RE.sub(keep, text)
    return re.sub(r"\s+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", clean)).strip(), cited


def source_dicts(labels: list[str], sources: list[Source]) -> list[dict]:
    by_label = {s.label: s for s in sources}
    return [by_label[label].as_dict() for label in labels if label in by_label]
