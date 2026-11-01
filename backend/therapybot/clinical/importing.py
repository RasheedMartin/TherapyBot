"""
Bringing a therapist's existing records into a client's record. An export from another system is often
one file holding many notes, so the text is split at note headers (a dated line such as "Progress Note -
03/14/2026" or "Date of Service: 2026-03-14") and each part gets a suggested date, type and title.

This is deliberately done in code, not by the model: it's predictable, fast, and the record isn't sent to
an external LLM just to be filed. The therapist reviews every suggestion before anything is saved.
"""

import re
from datetime import date

from django.db import transaction
from django.utils import timezone

from therapybot.models import Client, ClinicalDocument, Session

MAX_DOC_CHARS = 20000  # ClinicalDocument.text limit
MIN_SEGMENT_CHARS = 150  # shorter gaps between headers are one header block, not two notes
MAX_DOCUMENTS = 100

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE_RE = re.compile(
    r"\b(?:(?P<iso_y>\d{4})-(?P<iso_m>\d{1,2})-(?P<iso_d>\d{1,2})"
    r"|(?P<us_m>\d{1,2})/(?P<us_d>\d{1,2})/(?P<us_y>\d{2,4})"
    rf"|(?P<mdy_m>{_MONTH})\s+(?P<mdy_d>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<mdy_y>\d{{4}})"
    rf"|(?P<dmy_d>\d{{1,2}})\s+(?P<dmy_m>{_MONTH}),?\s+(?P<dmy_y>\d{{4}}))\b",
    re.IGNORECASE,
)
HEADER_WORDS = re.compile(
    r"progress note|session note|psychotherapy note|treatment note|clinical note|date of service|\bdos\b"
    r"|session date|visit date|note date|appointment|\bintake\b|assessment|\bsession\b|transcript",
    re.IGNORECASE,
)
BIRTH_WORDS = re.compile(r"\bdob\b|date of birth|birth ?date|\bborn\b", re.IGNORECASE)
TRANSCRIPT_LINE = re.compile(r"^\s*(t|c|therapist|client|counselor|patient|clinician)\s*:", re.IGNORECASE | re.MULTILINE)
INTAKE_WORDS = re.compile(r"\bintake\b|initial assessment|biopsychosocial|diagnostic assessment", re.IGNORECASE)
NOTE_WORDS = re.compile(
    r"progress note|session note|psychotherapy note|treatment note|\bsoap\b|\bdap\b|subjective|^\s*plan\s*:",
    re.IGNORECASE | re.MULTILINE,
)


def parse_date(match: re.Match) -> date | None:
    g = match.groupdict()
    try:
        if g["iso_y"]:
            y, m, d = int(g["iso_y"]), int(g["iso_m"]), int(g["iso_d"])
        elif g["us_y"]:
            y, m, d = int(g["us_y"]), int(g["us_m"]), int(g["us_d"])  # US order: month/day
            y += 2000 if y < 100 else 0
        elif g["mdy_y"]:
            y, m, d = int(g["mdy_y"]), _MONTHS[g["mdy_m"][:3].lower()], int(g["mdy_d"])
        else:
            y, m, d = int(g["dmy_y"]), _MONTHS[g["dmy_m"][:3].lower()], int(g["dmy_d"])
        found = date(y, m, d)
    except (ValueError, KeyError):
        return None
    # A note can't be from the future, and nothing here predates electronic records
    return found if date(1990, 1, 1) <= found <= timezone.localdate() else None


def find_date(text: str) -> date | None:
    """The first plausible date in the text, ignoring dates of birth."""
    for line in text.splitlines():
        if BIRTH_WORDS.search(line):
            continue
        for match in DATE_RE.finditer(line):
            if found := parse_date(match):
                return found
    return None


def _is_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 120 or BIRTH_WORDS.search(line) or not DATE_RE.search(line):
        return False
    without_dates = DATE_RE.sub("", line).strip(" -:|,.\t")
    return bool(HEADER_WORDS.search(line)) or len(without_dates) <= 12  # a line that is just a date


def _boundaries(lines: list[str]) -> list[int]:
    """Line indexes where a new note starts."""
    starts, last_offset, offset = [], None, 0
    offsets = []
    for line in lines:
        offsets.append(offset)
        offset += len(line) + 1
    for i, line in enumerate(lines):
        if not _is_header(line):
            continue
        start = i
        # Include a title line right above, e.g. "Progress Note" then "Date of Service: 03/14/2026"
        while start > 0 and start > i - 2 and lines[start - 1].strip() and len(lines[start - 1].strip()) <= 60 \
                and HEADER_WORDS.search(lines[start - 1]) and not DATE_RE.search(lines[start - 1]):
            start -= 1
        if last_offset is not None and offsets[start] - last_offset < MIN_SEGMENT_CHARS:
            continue
        starts.append(start)
        last_offset = offsets[start]
    return starts


def guess_type(text: str) -> str:
    head = text[:800]
    if len(TRANSCRIPT_LINE.findall(text)) >= 4:
        return ClinicalDocument.DocType.TRANSCRIPT
    if INTAKE_WORDS.search(head):
        return ClinicalDocument.DocType.INTAKE
    if NOTE_WORDS.search(text):
        return ClinicalDocument.DocType.PROGRESS_NOTE
    return ClinicalDocument.DocType.OTHER


def _title(doc_type: str, session_date: date | None, fallback: str) -> str:
    """Consistent titles across imports: "Progress note · Mar 14, 2026", or the file name if undated."""
    label = dict(ClinicalDocument.DocType.choices).get(doc_type, "Document")
    if session_date:
        return f"{label} · {session_date:%b} {session_date.day}, {session_date.year}"
    return f"{label} · {fallback}"[:120] if fallback else label


def _fit(text: str) -> list[str]:
    """Split text over the document size limit at paragraph breaks."""
    if len(text) <= MAX_DOC_CHARS:
        return [text]
    parts, current = [], ""
    for paragraph in re.split(r"(\n\s*\n)", text):
        if len(current) + len(paragraph) > MAX_DOC_CHARS and current:
            parts.append(current)
            current = ""
        while len(paragraph) > MAX_DOC_CHARS:  # one enormous paragraph
            parts.append(paragraph[:MAX_DOC_CHARS])
            paragraph = paragraph[MAX_DOC_CHARS:]
        current += paragraph
    if current.strip():
        parts.append(current)
    return parts


def split_records(text: str, filename: str = "") -> list[dict]:
    """Suggested documents for one uploaded file: [{"title", "doc_type", "session_date", "text"}]."""
    stem = re.sub(r"\.[a-z0-9]+$", "", filename or "", flags=re.IGNORECASE)
    lines = text.splitlines()
    starts = _boundaries(lines)
    if len(starts) >= 2:
        segments = []
        preamble = "\n".join(lines[: starts[0]]).strip()
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(lines)
            segments.append("\n".join(lines[start:end]).strip())
        # A short cover page (client name, export info) belongs with the first note, not on its own
        if preamble and len(preamble) < 300:
            segments[0] = f"{preamble}\n\n{segments[0]}"
        elif preamble:
            segments.insert(0, preamble)
    else:
        segments = [text.strip()]

    documents = []
    for segment in segments:
        if not segment:
            continue
        doc_type = guess_type(segment)
        session_date = find_date(segment[:400])
        parts = _fit(segment)
        for i, part in enumerate(parts, start=1):
            title = _title(doc_type, session_date, stem)
            documents.append({
                "title": (f"{title} (part {i} of {len(parts)})" if len(parts) > 1 else title)[:120],
                "doc_type": doc_type,
                "session_date": session_date.isoformat() if session_date else None,
                "text": part.strip(),
            })
    return documents[:MAX_DOCUMENTS]


SESSION_TYPES = (ClinicalDocument.DocType.PROGRESS_NOTE, ClinicalDocument.DocType.TRANSCRIPT,
                 ClinicalDocument.DocType.INTAKE)


def import_documents(*, client: Client, therapist, documents: list[dict]) -> dict:
    """
    Save reviewed documents into the record. Dated notes, transcripts and intakes are attached to the
    client's session on that date, creating a completed session if there isn't one, so session counts and
    the timeline reflect the therapist's history. Imported documents are final: they were signed in the
    system they came from.
    """
    created, sessions_created = [], 0
    with transaction.atomic():
        for doc in documents:
            session = None
            if doc["session_date"] and doc["doc_type"] in SESSION_TYPES:
                session = (
                    Session.objects.filter(client=client, date=doc["session_date"])
                    .exclude(status=Session.Status.CANCELLED).first()
                )
                if session is None:
                    session = Session.objects.create(
                        client=client, therapist=therapist, date=doc["session_date"],
                        status=Session.Status.COMPLETED,
                    )
                    sessions_created += 1
            created.append(ClinicalDocument.objects.create(
                client=client, author=therapist, session=session, session_date=doc["session_date"],
                doc_type=doc["doc_type"], status=ClinicalDocument.Status.FINAL, title=doc["title"],
                text=doc["text"], imported_from=doc.get("filename", "")[:255],
            ))
    return {"documents": created, "sessions_created": sessions_created}
