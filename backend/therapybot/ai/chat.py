"""The client-facing companion: safety screening, retrieval, and the chat reply itself."""

from therapybot import llm, rag, safety
from therapybot.ai.prompts import SUMMARY_PROMPT, SYSTEM_PROMPT


def _build_messages(question: str, therapy_type: str, history, user_context: str, sources: list | None = None):
    # Short follow-ups ("what if that doesn't work?") retrieve better with the previous user turn
    previous = next((content for role, content in reversed(history or []) if role == "user"), "")
    context = rag.retrieve_context(f"{previous}\n{question}".strip(), sources=sources)

    system = SYSTEM_PROMPT.format(therapy_type=therapy_type, context=context, user_context=user_context)
    messages = [llm.system(system)]
    for role, content in history or []:
        messages.append(llm.user(content) if role == "user" else llm.assistant(content))
    messages.append(llm.user(question))
    return messages


def _prepare(question, therapy_type, history, user_context, sources, assessment):
    """Screen the message, then build the model input. Returns None when the crisis response should be used."""
    details = {}
    risk = safety.assess_risk(question, history, details)
    if assessment is not None:
        assessment["risk"] = risk
        assessment["emergency"] = risk == "imminent" and details.get("in_progress", False)
        # Feature hand-offs are offered only when there's no safety concern
        assessment["next_step"] = details.get("next_step", "") if risk == "none" else ""
    if risk == "imminent":
        return None
    if risk == "elevated":
        user_context += safety.ELEVATED_RISK_NOTE
    return _build_messages(question, therapy_type, history, user_context, sources)


def _crisis_reply(assessment: dict) -> str:
    return safety.EMERGENCY_RESPONSE if assessment.get("emergency") else safety.CRISIS_RESPONSE


def therapy_chat(
    question: str,
    therapy_type: str = "General Therapy",
    history=None,
    user_context: str = "",
    sources=None,
    assessment: dict | None = None,
) -> tuple[str, bool]:
    """
    Answer a user message. `history` is a list of (role, content) tuples, oldest first.
    Returns (reply, is_crisis). Related articles are appended to `sources` and the risk level is
    stored in `assessment["risk"]` when those are given.
    """
    assessment = {} if assessment is None else assessment
    messages = _prepare(question, therapy_type, history, user_context, sources, assessment)
    if messages is None:
        return _crisis_reply(assessment), True
    return llm.get_chat_model().complete(messages), False


def therapy_chat_stream(
    question: str,
    therapy_type: str = "General Therapy",
    history=None,
    user_context: str = "",
    sources=None,
    assessment: dict | None = None,
):
    """Like therapy_chat, but yields the reply in text chunks as the model produces them."""
    assessment = {} if assessment is None else assessment
    messages = _prepare(question, therapy_type, history, user_context, sources, assessment)
    if messages is None:
        yield _crisis_reply(assessment)
        return
    yield from llm.get_chat_model().stream(messages)


def summarize_conversation(previous_summary: str, messages) -> str:
    """Fold older (role, content) messages into the running summary."""
    transcript = "\n".join(f"{'User' if role == 'user' else 'Assistant'}: {content}" for role, content in messages)
    prompt = f"Current summary:\n{previous_summary or '(none yet)'}\n\nNew messages to fold in:\n{transcript}\n\nUpdated summary:"
    return llm.get_chat_model(fast=True).complete([llm.system(SUMMARY_PROMPT), llm.user(prompt)])[:2000]
