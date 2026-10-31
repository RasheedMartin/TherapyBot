"""
Therapist-facing AI: session prep, asking the record, progress-note drafts, and treatment-plan drafts.
Every output is grounded in the client's record (read through rag.retrieval, which authorizes and audits)
and citations are validated server-side. Client text is sent to the configured LLM provider.
"""

import logging

from therapybot import audit, llm, safety
from therapybot.ai.drafting import complete_json
from therapybot.clinical import prompts
from therapybot.clinical.citations import label_chunks, render_sources, source_dicts, validate_items, validate_text
from therapybot.clinical.facts import client_facts, render_facts
from therapybot.models import Client
from therapybot.rag import recent_client_chunks, search_client_record

logger = logging.getLogger(__name__)

NOT_FOUND = "I couldn't find that in this client's record."
TREATMENT_QUERIES = [
    "presenting problem, symptoms and concerns",
    "goals the client wants to work on",
    "interventions, skills and homework used so far",
    "progress, barriers, and what helped",
]


def _user_prompt(facts: dict, sources, request_text: str) -> str:
    return f"FACTS\n{render_facts(facts)}\n\nSOURCES\n{render_sources(sources)}\n\n{request_text}"


def session_prep(*, actor, client: Client, request=None) -> dict:
    chunks = recent_client_chunks(actor=actor, client_id=client.pk, documents=3, request=request, purpose="ai.prep")
    facts = client_facts(client, actor)
    sources = label_chunks(chunks)
    result = {"facts": facts, "summary": "", "last_session": [], "open_threads": [], "suggested_focus": [],
              "sources": [], "dropped_claims": 0}
    if sources:
        raw = complete_json(
            [llm.system(prompts.PREP_PROMPT), llm.user(_user_prompt(facts, sources, "Prepare the session brief."))],
            "Session prep",
        )
        result["summary"], cited = validate_text(str(raw.get("summary", "")), sources)
        for key in ("last_session", "open_threads", "suggested_focus"):
            result[key], dropped = validate_items(raw.get(key), sources)
            result["dropped_claims"] += dropped
            cited += [label for item in result[key] for label in item["sources"]]
        result["sources"] = source_dicts(list(dict.fromkeys(cited)), sources)
    audit.record(actor, "ai.prep", request=request, client=client, sources=len(result["sources"]),
                 dropped_claims=result["dropped_claims"])
    return result


def ask_record(*, actor, client: Client, question: str, request=None) -> dict:
    chunks = search_client_record(actor=actor, client_id=client.pk, query=question, k=8, request=request,
                                  purpose="ai.ask")
    sources = label_chunks(chunks)
    answer, cited = NOT_FOUND, []
    if sources:
        raw = llm.get_chat_model().complete([
            llm.system(prompts.ASK_PROMPT),
            llm.user(_user_prompt(client_facts(client, actor), sources, f"QUESTION\n{question}")),
        ])
        answer, cited = validate_text(raw, sources)
        # An answer that cites nothing isn't grounded in the record; don't present it as if it were
        if not cited:
            answer = NOT_FOUND
    audit.record(actor, "ai.ask", request=request, client=client, sources=len(cited))
    return {"answer": answer, "sources": source_dicts(cited, sources)}


def draft_progress_note(*, actor, client: Client, source_text: str, note_format: str, request=None) -> dict:
    """Draft SOAP/DAP sections from a transcript or rough notes. Returns sections + review flags (unsaved)."""
    note_format = note_format if note_format in prompts.NOTE_SECTIONS else "soap"
    spec = prompts.NOTE_SECTIONS[note_format]
    section_spec = ", ".join(f'"{name}": "{hint}"' for name, hint in spec.items())
    raw = complete_json(
        [
            llm.system(prompts.NOTE_PROMPT.format(format_name=note_format.upper(), section_spec=section_spec)),
            llm.user(f"SOURCE TEXT\n{source_text}\n\nDraft the note as JSON."),
        ],
        "Progress note draft",
    )
    sections = raw.get("sections") if isinstance(raw.get("sections"), dict) else {}
    result = {name: str(sections.get(name) or "Not documented in source.").strip() for name in spec}
    flags = [
        str(f).strip() for f in raw.get("review_flags", [])
        if str(f).strip() and not str(f).strip().startswith("<")  # drop echoed placeholders
    ][:8]
    # Don't rely on the model alone to notice risk content in the source
    if safety.mentions_risk(source_text):
        flags.insert(0, "The source mentions suicide or self-harm: confirm the risk assessment and safety plan are documented.")
    audit.record(actor, "ai.draft_note", request=request, client=client, format=note_format, flags=len(flags))
    return {"format": note_format, "sections": result, "review_flags": flags}


def render_note(note_format: str, sections: dict) -> str:
    return "\n\n".join(f"## {name.title()}\n{text}" for name, text in sections.items())


def draft_treatment_plan(*, actor, client: Client, modality_label: str, request=None) -> dict:
    """Goals, objectives and interventions drawn from the record, each goal cited (unsaved)."""
    seen, chunks = set(), []
    for query in TREATMENT_QUERIES:
        for chunk in search_client_record(actor=actor, client_id=client.pk, query=query, k=4, request=request,
                                          purpose="ai.draft_treatment_plan"):
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                chunks.append(chunk)
    sources = label_chunks(chunks[:12])
    if not sources:
        return {"problem_summary": "", "goals": [], "sources": [], "dropped_claims": 0}
    raw = complete_json(
        [
            llm.system(prompts.TREATMENT_PROMPT.format(modality=modality_label)),
            llm.user(_user_prompt(client_facts(client, actor), sources, "Draft the treatment plan.")),
        ],
        "Treatment plan draft",
    )
    summary, cited = validate_text(str(raw.get("problem_summary", "")), sources)
    goals, dropped = [], 0
    for goal in raw.get("goals", []) if isinstance(raw.get("goals"), list) else []:
        kept, lost = validate_items([goal], sources)
        if not kept:
            dropped += lost
            continue
        objectives = [
            {
                "text": str(o.get("text", "")).strip(),
                "measure": str(o.get("measure", "")).strip()[:200],
                "interventions": [str(i).strip() for i in o.get("interventions", []) if str(i).strip()][:6],
            }
            for o in goal.get("objectives", []) if isinstance(o, dict) and str(o.get("text", "")).strip()
        ][:3]
        goals.append({**kept[0], "objectives": objectives})
        cited += kept[0]["sources"]
    audit.record(actor, "ai.draft_treatment_plan", request=request, client=client, goals=len(goals),
                 dropped_claims=dropped)
    return {"problem_summary": summary, "goals": goals[:3],
            "sources": source_dicts(list(dict.fromkeys(cited)), sources), "dropped_claims": dropped}


def evidence_for(labels: list[str], sources_payload: list[dict]) -> list[dict]:
    by_label = {s["label"]: s for s in sources_payload}
    return [by_label[label] for label in labels if label in by_label]


