"""Crisis detection: keyword floors plus a fast model screener. Changes here must keep the safety tests green."""

import json
import logging
import re

from therapybot import llm

logger = logging.getLogger(__name__)

# First-person statements of intent: always answered with crisis resources, no model needed
CRISIS_PATTERNS = [
    r"\bkill(ing)? myself\b",
    r"\bend(ing)? (my|it all|my own) li(fe|ves)\b",
    r"\bend it all\b",
    r"\bwant(ed)? to die\b",
    r"\bwish i (was|were) dead\b",
    r"\b(hurt(ing)?|harm(ing)?|cut(ting)?) myself\b",
    r"\bdon'?t want to (live|be alive|be here)\b",
    r"\bnot worth living\b",
    r"\bno reason to live\b",
    r"\bbetter off dead\b",
]
_CRISIS_RE = re.compile("|".join(CRISIS_PATTERNS), re.IGNORECASE)

# Mentions of the topic (e.g. grief after a suicide): at least "elevated" care, and the screener can escalate
RISK_TOPIC_PATTERNS = [r"\bsuicid(e|al)\b", r"\bself[- ]?harm(ing)?\b", r"\boverdos(e|ed|ing)\b"]
_RISK_TOPIC_RE = re.compile("|".join(RISK_TOPIC_PATTERNS), re.IGNORECASE)

CRISIS_RESPONSE = """I'm really concerned about what you've shared, and I'm glad you said something. If you're having thoughts of suicide or self-harm, please reach out for immediate support:

- **988 Suicide & Crisis Lifeline** — call or text **988** (US)
- **Crisis Text Line** — text **HOME** to **741741**
- **Emergency services** — call **911** if you are in immediate danger
- Outside the US, find a local helpline at [findahelpline.com](https://findahelpline.com)

You don't have to face this alone. These services are free, confidential, and available 24/7, and the people there are trained to help in ways I can't."""

EMERGENCY_RESPONSE = """Please get emergency help right now.

- **Call 911** (or your local emergency number), or have someone take you to the nearest emergency room.
- If you took pills or another substance, **Poison Control: 1-800-222-1222** (US) can tell you what to do immediately.
- If you can, tell someone near you what's happening and don't stay alone.

When you're safe, the **988 Suicide & Crisis Lifeline** (call or text 988) is there for you 24/7. You matter, and help is available right now."""

RISK_PROMPT = """You are a safety screener for a mental-health support chat. Rate the risk in the user's LATEST message,
using the earlier messages only as context.

- "imminent": intent, plan, or means to end their life or seriously harm themselves or someone else, or a current
  emergency (e.g. "I took a bunch of pills", "tonight's the night", "I have the rope ready").
- "elevated": indirect or passive signs of suicidal thinking or self-harm, hopelessness about living, or feeling like a
  burden (e.g. "everyone would be better off without me", "I won't be a problem much longer", "what's the point anymore").
- "none": everything else, including ordinary sadness, stress, anger, or talking about someone else's past.

Also set "in_progress" to true only if harm has already started or is happening now (e.g. they already took
pills or are injuring themselves), otherwise false.

Finally, set "next_step" to what the user is asking for, if it matches one of these app features:
- "find_care": they want to see or find a therapist, counselor, psychiatrist, or other professional
- "plan": they want a routine, habit, schedule, or plan to stick to
- "notes": they want help understanding notes or a summary from their therapist or doctor
- "none": anything else

Reply with JSON only: {"risk": "none" | "elevated" | "imminent", "in_progress": true | false,
"next_step": "find_care" | "plan" | "notes" | "none"}"""

ELEVATED_RISK_NOTE = """
Safety note: the user's latest message may signal suicidal thinking or self-harm, even if indirectly. Respond with
warmth and without alarm. Gently and directly ask whether they're having thoughts of ending their life or hurting
themselves, and let them know they deserve support right now. Always include one brief, natural mention that they
can call or text 988 (US) any time, even if they seem okay. Stay in the conversation; don't just hand them a number."""


def is_crisis_message(text: str) -> bool:
    return bool(_CRISIS_RE.search(text))


def assess_risk(question: str, history=None, details: dict | None = None) -> str:
    """
    'none' | 'elevated' | 'imminent'. Keywords set a floor the model can only raise: first-person intent is
    always 'imminent', topic mentions at least 'elevated'. If the model fails, a topic mention is treated as
    'imminent' (the safe default) and anything else as 'none'.
    """
    if is_crisis_message(question):
        return "imminent"
    topic = bool(_RISK_TOPIC_RE.search(question))

    recent = "\n".join(f"{role}: {content[:500]}" for role, content in (history or [])[-4:])
    messages = [
        llm.system(RISK_PROMPT),
        llm.user(f"Earlier messages:\n{recent or '(none)'}\n\nLatest user message:\n{question}"),
    ]
    try:
        raw = llm.get_chat_model(fast=True).complete(messages)
        parsed = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        risk = parsed.get("risk", "none")
        if details is not None:
            details["in_progress"] = parsed.get("in_progress") is True
            step = parsed.get("next_step")
            details["next_step"] = step if step in ("find_care", "plan", "notes") else ""
    except Exception:
        logger.warning("Risk screening failed; relying on keyword check", exc_info=True)
        return "imminent" if topic else "none"
    if risk not in ("none", "elevated", "imminent"):
        risk = "imminent" if topic else "none"
    if topic and risk == "none":
        risk = "elevated"
    return risk
