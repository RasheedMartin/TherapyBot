"""
LlamaIndex + Groq integration: retrieval over a curated knowledge base plus a
multi-turn chat completion with safety guardrails.
"""

import json
import logging
import os
import re
import threading
from pathlib import Path

import certifi
from django.conf import settings

logger = logging.getLogger(__name__)

INDEX_DIR = Path(settings.BASE_DIR) / "storage"
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")
EMBED_CACHE_DIR = Path(os.getenv("FASTEMBED_CACHE_PATH", Path(settings.BASE_DIR) / ".fastembed_cache"))
KNOWLEDGE_DIR = Path(settings.BASE_DIR) / "knowledge"
# Showing a link is a stronger claim than informing a reply, so it needs a clearer match
MIN_SOURCE_RELEVANCE = float(os.getenv("RAG_MIN_SOURCE_RELEVANCE", "0.6"))
# Chunks scoring below this cosine similarity are treated as off-topic and not shown to the model
MIN_RELEVANCE = float(os.getenv("RAG_MIN_RELEVANCE", "0.5"))  # calibrated for bge-small-en-v1.5

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

SYSTEM_PROMPT = """You are TherapyBot, a warm, grounded support companion. This conversation's focus is {therapy_type}.

How to talk:
- This is a chat, not an article. Write like you're texting a friend who happens to know a lot about mental health: plain sentences, no headings, no bold, no lists unless the user asks for steps or options.
- Keep it short. Usually 1-3 sentences, never more than about 80 words unless the user asks for detail. A short message gets a short reply.
- Be curious before being helpful. Reflect what you heard in your own words and ask one open question, especially early on or when things are unclear.
- When you suggest something, suggest one small thing, tailored to what they've told you, and check whether it fits.
- End with at most one question. Don't end every message with a question; sometimes just acknowledge.
- Vary your openings. Never start with "It sounds like" twice in a conversation.
- Build on what was said earlier in the conversation.

Helpful next steps (TherapyBot features; link them with exactly these Markdown links):
- [Find care](/find-care): licensed therapists near them on a map, with a script for the first call. If they want to see a professional or ask how to find one, your reply MUST include this link.
- [Plans](/plans): turn an idea into a small daily routine with reminders. If they want a routine, habit, or plan, include this link.
- [Notes](/notes): plain-language explanations of their therapist's notes.
Offer one when it would genuinely help; don't push.

Boundaries:
- You are not a therapist and do not diagnose or treat. When difficulties are persistent, severe, or beyond self-help, gently encourage professional support.
- If the user mentions suicide, self-harm, or being in danger, prioritise their safety: urge them to call or text 988 (US) or local emergency services now.
- Never invent statistics, studies, or sources.
{user_context}
{context}"""

_llm = None
_embeddings_configured = False
_index = None
_index_mtime = None
_index_lock = threading.Lock()


def is_crisis_message(text: str) -> bool:
    return bool(_CRISIS_RE.search(text))


def _configure_embeddings():
    global _embeddings_configured
    if _embeddings_configured:
        return

    from llama_index.core import Settings
    from llama_index.embeddings.fastembed import FastEmbedEmbedding

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    # Runs locally on CPU (ONNX). Must match the model the persisted index was built with.
    Settings.embed_model = FastEmbedEmbedding(model_name=EMBED_MODEL_NAME, cache_dir=str(EMBED_CACHE_DIR))
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50
    _embeddings_configured = True


def get_llm():
    global _llm
    if _llm is None:
        from llama_index.llms.groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable not set")
        # gpt-oss models reason before answering; keep that brief and leave room for the reply
        extra = {"reasoning_effort": "low"} if "gpt-oss" in settings.GROQ_MODEL else {}
        _llm = Groq(
            model=settings.GROQ_MODEL,
            temperature=0.6,
            max_tokens=1500,
            api_key=api_key,
            additional_kwargs=extra,
            timeout=30,
            max_retries=1,
        )
    return _llm


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a `---`-delimited `key: value` header from a Markdown body."""
    if not text.startswith("---"):
        return {}, text
    header, _, body = text[3:].partition("\n---")
    meta = {}
    for line in header.strip().splitlines():
        key, sep, value = line.partition(":")
        if sep and value.strip():
            meta[key.strip()] = value.strip()
    return meta, body.lstrip("\n")


def load_knowledge_documents():
    """Skill guides from KNOWLEDGE_DIR plus active reference articles from the database."""
    from llama_index.core import Document

    from therapybot.models import KnowledgeArticle

    documents = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta, body = _parse_front_matter(path.read_text(encoding="utf-8"))
        # The H1 just repeats the title (kept in metadata); alone it would become an empty chunk
        body = re.sub(r"\A# .*\n+", "", body)
        # Guard against indexing error pages or other junk
        if len(body) < 200 or "<html" in body.lower() or "403 forbidden" in body.lower():
            raise ValueError(f"{path.name} doesn't look like a knowledge article; refusing to index it")
        meta.setdefault("title", path.stem.replace("-", " "))
        meta["file_name"] = path.name
        documents.append(Document(text=body, metadata=meta, id_=path.name))

    for article in KnowledgeArticle.objects.filter(active=True):
        documents.append(
            Document(
                text=article.body,
                metadata={"title": article.title, "url": article.url, "source": article.source},
                id_=f"article-{article.pk}",
            )
        )
    if not documents:
        raise ValueError(f"No knowledge articles found in {KNOWLEDGE_DIR} or the database")
    return documents


def _content_hash(documents) -> str:
    import hashlib

    digest = hashlib.sha256(EMBED_MODEL_NAME.encode())
    for doc in sorted(documents, key=lambda d: d.id_):
        digest.update(doc.id_.encode())
        digest.update(doc.text.encode())
        digest.update(json.dumps(doc.metadata, sort_keys=True).encode())
    return digest.hexdigest()


MANIFEST = INDEX_DIR / "manifest.json"


def build_index(if_stale: bool = False):
    """Embed all knowledge documents and persist the index. With if_stale, skip when nothing changed."""
    from llama_index.core import VectorStoreIndex
    from llama_index.core.node_parser import MarkdownNodeParser

    global _index, _index_mtime
    documents = load_knowledge_documents()
    content_hash = _content_hash(documents)
    if if_stale and MANIFEST.exists() and json.loads(MANIFEST.read_text()).get("hash") == content_hash:
        logger.info("Knowledge index is up to date")
        return None

    _configure_embeddings()
    logger.info("Building index from %d knowledge documents", len(documents))
    index = VectorStoreIndex.from_documents(documents, transformations=[MarkdownNodeParser()], show_progress=False)
    index.storage_context.persist(persist_dir=str(INDEX_DIR))
    MANIFEST.write_text(json.dumps({"hash": content_hash, "documents": len(documents)}))
    _index, _index_mtime = index, MANIFEST.stat().st_mtime
    logger.info("Index saved to %s", INDEX_DIR)
    return index


def get_index():
    """Load the persisted index, reloading when another process has rebuilt it. Returns None if unavailable."""
    global _index, _index_mtime
    mtime = MANIFEST.stat().st_mtime if MANIFEST.exists() else None
    if _index is not None and mtime == _index_mtime:
        return _index
    with _index_lock:
        if (_index is None or mtime != _index_mtime) and (INDEX_DIR / "docstore.json").exists():
            from llama_index.core import StorageContext, load_index_from_storage

            _configure_embeddings()
            _index = load_index_from_storage(StorageContext.from_defaults(persist_dir=str(INDEX_DIR)))
            _index_mtime = mtime
            logger.info("Loaded vector index from %s", INDEX_DIR)
    return _index


def retrieve_context(query: str, top_k: int = 3, sources: list | None = None) -> str:
    """
    Best-effort retrieval of on-topic reference material; returns "" if none applies.
    Articles with a public URL that were used are appended to `sources` for "related reading".
    """
    if len(query.split()) < 4:
        return ""  # greetings and one-word replies embed too vaguely to retrieve anything useful
    try:
        index = get_index()
        if index is None:
            return ""
        nodes = index.as_retriever(similarity_top_k=top_k).retrieve(query)
    except Exception:
        logger.error("Context retrieval failed; answering without it", exc_info=True)
        return ""

    from therapybot.articles import passes_topic_gate

    sections = []
    for n in nodes:
        text = n.node.get_content().strip()
        meta = n.node.metadata
        score = n.score if n.score is not None else 1.0
        # Topic-specific articles (e.g. suicide, eating disorders) are only used when the user raised the topic
        if not text or score < MIN_RELEVANCE or not passes_topic_gate(meta.get("url"), query):
            continue
        sections.append(f"[{meta.get('title', 'Reference')}]\n{text}")
        # Offer at most one article to read, and only a strong match
        if sources is not None and not sources and meta.get("url") and score >= MIN_SOURCE_RELEVANCE:
            sources.append({"title": meta["title"], "url": meta["url"], "source": meta.get("source", "")})
    if not sections:
        return ""
    joined = "\n\n---\n\n".join(sections)
    return (
        "Background notes you may draw on if they genuinely fit what the user needs right now. "
        "Pick at most one or two ideas, put them in your own words, and never mention these notes.\n\n"
        f"{joined}"
    )


def _build_messages(question: str, therapy_type: str, history, user_context: str, sources: list | None = None):
    from llama_index.core.llms import ChatMessage, MessageRole

    # Short follow-ups ("what if that doesn't work?") retrieve better with the previous user turn
    previous = next((content for role, content in reversed(history or []) if role == "user"), "")
    context = retrieve_context(f"{previous}\n{question}".strip(), sources=sources)

    system = SYSTEM_PROMPT.format(therapy_type=therapy_type, context=context, user_context=user_context)
    messages = [ChatMessage(role=MessageRole.SYSTEM, content=system)]
    for role, content in history or []:
        messages.append(
            ChatMessage(role=MessageRole.USER if role == "user" else MessageRole.ASSISTANT, content=content)
        )
    messages.append(ChatMessage(role=MessageRole.USER, content=question))
    return messages


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

_fast_llm = None


def get_fast_llm():
    """A smaller, faster model for background tasks (risk screening, summaries)."""
    global _fast_llm
    if _fast_llm is None:
        from llama_index.llms.groq import Groq

        extra = {"reasoning_effort": "low"} if "gpt-oss" in settings.GROQ_FAST_MODEL else {}
        _fast_llm = Groq(
            model=settings.GROQ_FAST_MODEL,
            temperature=0,
            max_tokens=400,
            api_key=os.getenv("GROQ_API_KEY"),
            additional_kwargs=extra,
            timeout=8,
            max_retries=0,
        )
    return _fast_llm


def assess_risk(question: str, history=None, details: dict | None = None) -> str:
    """
    'none' | 'elevated' | 'imminent'. Keywords set a floor the model can only raise: first-person intent is
    always 'imminent', topic mentions at least 'elevated'. If the model fails, a topic mention is treated as
    'imminent' (the safe default) and anything else as 'none'.
    """
    if is_crisis_message(question):
        return "imminent"
    topic = bool(_RISK_TOPIC_RE.search(question))
    from llama_index.core.llms import ChatMessage, MessageRole

    recent = "\n".join(f"{role}: {content[:500]}" for role, content in (history or [])[-4:])
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=RISK_PROMPT),
        ChatMessage(role=MessageRole.USER, content=f"Earlier messages:\n{recent or '(none)'}\n\nLatest user message:\n{question}"),
    ]
    try:
        raw = get_fast_llm().chat(messages).message.content or ""
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


def _prepare(question, therapy_type, history, user_context, sources, assessment):
    """Screen the message, then build the model input. Returns None when the crisis response should be used."""
    details = {}
    risk = assess_risk(question, history, details)
    if assessment is not None:
        assessment["risk"] = risk
        assessment["emergency"] = risk == "imminent" and details.get("in_progress", False)
        # Feature hand-offs are offered only when there's no safety concern
        assessment["next_step"] = details.get("next_step", "") if risk == "none" else ""
    if risk == "imminent":
        return None
    if risk == "elevated":
        user_context += ELEVATED_RISK_NOTE
    return _build_messages(question, therapy_type, history, user_context, sources)


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
        return (EMERGENCY_RESPONSE if assessment.get("emergency") else CRISIS_RESPONSE), True
    response = get_llm().chat(messages)
    return (response.message.content or "").strip(), False


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
        yield EMERGENCY_RESPONSE if assessment.get("emergency") else CRISIS_RESPONSE
        return
    for chunk in get_llm().stream_chat(messages):
        if chunk.delta:
            yield chunk.delta


SUMMARY_PROMPT = """Update the running summary of a supportive conversation so the assistant can remember it later.
Keep what matters for continuing to help: what the person is going through, people and situations they mentioned,
feelings, what they've tried, what helped or didn't, and any goals or commitments. Leave out small talk.
Write in the third person ("They..."), at most 150 words, plain prose."""


def summarize_conversation(previous_summary: str, messages) -> str:
    """Fold older (role, content) messages into the running summary."""
    from llama_index.core.llms import ChatMessage, MessageRole

    transcript = "\n".join(f"{'User' if role == 'user' else 'Assistant'}: {content}" for role, content in messages)
    prompt = f"Current summary:\n{previous_summary or '(none yet)'}\n\nNew messages to fold in:\n{transcript}\n\nUpdated summary:"
    response = get_fast_llm().chat(
        [ChatMessage(role=MessageRole.SYSTEM, content=SUMMARY_PROMPT), ChatMessage(role=MessageRole.USER, content=prompt)]
    )
    return (response.message.content or "").strip()[:2000]


PLAN_PROMPT = """You help people turn a supportive conversation into a small, realistic action plan they can actually stick to.

Read the conversation and draft a plan based on what the user wants and what was discussed. Rules:
- 2 to 5 steps. Small, concrete, and doable even on a hard day ("Walk for 10 minutes after lunch", not "Exercise more").
- Use techniques that came up in the conversation where possible. Don't add anything clinical, diagnostic, or medication-related.
- If seeing a professional came up, include a one-time step like "Call one therapist from my shortlist" with "action": "find_care".
- Write in the user's voice ("Try box breathing before bed"), warm and plain.

Reply with JSON only, no other text, in exactly this shape:
{{"title": "short plan name, max 60 chars",
  "summary": "one sentence on what this plan is for",
  "steps": [{{"title": "the action, max 80 chars",
             "details": "one sentence on how or why",
             "frequency": "once" | "daily" | "weekdays" | "weekly",
             "weekday": 0-6 for weekly steps (0 = Monday), otherwise null,
             "time_of_day": "HH:MM" in 24h if a time makes sense, otherwise null,
             "action": "find_care" for steps about finding or contacting a therapist, otherwise ""}}]}}
{user_context}"""


def draft_plan(history, therapy_type: str = "General Therapy", user_context: str = "") -> dict:
    """Draft a plan (unsaved) from conversation history. Raises ValueError if the model output is unusable."""
    from llama_index.core.llms import ChatMessage, MessageRole

    transcript = "\n\n".join(f"{'User' if role == 'user' else 'TherapyBot'}: {content}" for role, content in history)
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=PLAN_PROMPT.format(user_context=user_context)),
        ChatMessage(
            role=MessageRole.USER,
            content=f"Conversation focus: {therapy_type}\n\nConversation:\n{transcript}\n\nDraft the plan as JSON.",
        ),
    ]
    raw = (get_llm().chat(messages).message.content or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Plan draft was not JSON")
    plan = json.loads(raw[start : end + 1])
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise ValueError("Plan draft had no steps")
    return plan


NOTES_PROMPT = """You help someone understand notes or an after-visit summary written by their own therapist, counselor, or doctor.

Rules:
- Stay faithful to the notes. Explain what is written; never add diagnoses, treatments, or advice that contradicts the clinician.
- Plain, warm language at about an 8th-grade reading level. Address the reader as "you" and the clinician as "your therapist" (or their role). Never write "we" as if you were in the session.
- If something is unclear, say so and suggest asking the clinician rather than guessing.
- If the notes mention safety planning, self-harm, or suicide risk, include in the summary that they can call or text 988 (US) any time.
- Homework: only exercises or tasks the notes actually assign, written as small concrete steps.
- Questions: 2-4 thoughtful questions the person might ask at their next session.

Reply with JSON only, in exactly this shape:
{{"title": "short label for these notes, max 60 chars",
  "summary": "2-4 sentence plain-language summary",
  "key_points": ["short point", ...],
  "terms": [{{"term": "clinical word or abbreviation", "meaning": "plain explanation"}}],
  "homework": [{{"title": "max 80 chars", "details": "one sentence", "frequency": "once" | "daily" | "weekdays" | "weekly",
                "weekday": 0-6 for weekly (0 = Monday) else null, "time_of_day": "HH:MM" or null}}],
  "questions": ["question", ...]}}
{user_context}"""


def explain_notes(text: str, user_context: str = "") -> dict:
    """Plain-language explanation of clinician notes. Raises ValueError if the model output is unusable."""
    from llama_index.core.llms import ChatMessage, MessageRole

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=NOTES_PROMPT.format(user_context=user_context)),
        ChatMessage(role=MessageRole.USER, content=f"Here are my notes:\n\n{text}\n\nExplain them as JSON."),
    ]
    raw = (get_llm().chat(messages).message.content or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Notes explanation was not JSON")
    result = json.loads(raw[start : end + 1])
    if not isinstance(result, dict) or not result.get("summary"):
        raise ValueError("Notes explanation had no summary")
    return result
