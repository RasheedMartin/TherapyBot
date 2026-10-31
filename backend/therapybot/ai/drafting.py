"""Structured drafts produced by the model as JSON: plans from conversations, explanations of notes."""

import json

from therapybot import llm
from therapybot.ai.prompts import NOTES_PROMPT, PLAN_PROMPT


def complete_json(messages: list[llm.ChatMessage], what: str) -> dict:
    """Run the main model and parse the first JSON object in its reply. Raises ValueError if there isn't one."""
    raw = llm.get_chat_model().complete(messages)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"{what} was not JSON")
    result = json.loads(raw[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError(f"{what} was not a JSON object")
    return result


def draft_plan(history, therapy_type: str = "General Therapy", user_context: str = "") -> dict:
    """Draft a plan (unsaved) from conversation history. Raises ValueError if the model output is unusable."""
    transcript = "\n\n".join(f"{'User' if role == 'user' else 'TherapyBot'}: {content}" for role, content in history)
    plan = complete_json(
        [
            llm.system(PLAN_PROMPT.format(user_context=user_context)),
            llm.user(f"Conversation focus: {therapy_type}\n\nConversation:\n{transcript}\n\nDraft the plan as JSON."),
        ],
        "Plan draft",
    )
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise ValueError("Plan draft had no steps")
    return plan


def explain_notes(text: str, user_context: str = "") -> dict:
    """Plain-language explanation of clinician notes. Raises ValueError if the model output is unusable."""
    result = complete_json(
        [
            llm.system(NOTES_PROMPT.format(user_context=user_context)),
            llm.user(f"Here are my notes:\n\n{text}\n\nExplain them as JSON."),
        ],
        "Notes explanation",
    )
    if not result.get("summary"):
        raise ValueError("Notes explanation had no summary")
    return result
