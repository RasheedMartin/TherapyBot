"""
The AI features views call into. Views use `ai.<function>` so tests can patch these names here.

Model access lives in therapybot.llm, retrieval in therapybot.rag, crisis handling in therapybot.safety.
"""

from therapybot.ai.chat import summarize_conversation, therapy_chat, therapy_chat_stream
from therapybot.ai.drafting import draft_plan, explain_notes
from therapybot.safety import is_crisis_message

__all__ = [
    "draft_plan",
    "explain_notes",
    "is_crisis_message",
    "summarize_conversation",
    "therapy_chat",
    "therapy_chat_stream",
]
