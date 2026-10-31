"""
Import reference articles from MedlinePlus (U.S. National Library of Medicine) via its official
web service: https://medlineplus.gov/about/developers/webservices/

Health topic summaries are written by NLM and may be reused with attribution; we always link back
to the original page. The service allows 85 requests per minute per IP.
"""

import html
import logging
import re
import time
import xml.etree.ElementTree as ET

import requests

from therapybot.models import KnowledgeArticle

logger = logging.getLogger(__name__)

API_URL = "https://wsearch.nlm.nih.gov/ws/query"
SOURCE = "MedlinePlus"
SEARCH_TERMS = [
    "anxiety",
    "depression",
    "stress",
    "insomnia",
    "panic disorder",
    "post-traumatic stress disorder",
    "bereavement",
    "mental health",
    "teen mental health",
    "child mental health",
    "obsessive-compulsive disorder",
    "bipolar disorder",
    "attention deficit hyperactivity disorder",
    "phobias",
    "eating disorders",
    "seasonal affective disorder",
    "postpartum depression",
    "alcohol use disorder",
    "substance use disorder",
    "caregiver health",
    "suicide",
]


# Topics that are only relevant (or safe to raise) when the user brings them up themselves.
# Maps a MedlinePlus URL to words, at least one of which must appear in the user's message.
TOPIC_GATES = {
    "https://medlineplus.gov/suicide.html": ("suicid", "kill myself", "end my life", "want to die"),
    "https://medlineplus.gov/eatingdisorders.html": ("eat", "food", "binge", "purg", "weight", "anorex", "bulim", "meal"),
    "https://medlineplus.gov/druguseandaddiction.html": ("drug", "substance", "addict", "high", "pills", "using"),
    "https://medlineplus.gov/alcoholusedisorderaud.html": ("alcohol", "drink", "drunk", "beer", "wine"),
    "https://medlineplus.gov/postpartumdepression.html": ("baby", "postpartum", "pregnan", "birth", "newborn"),
    "https://medlineplus.gov/teenmentalhealth.html": ("teen", "adolescent", "son", "daughter", "kid", "high school"),
    "https://medlineplus.gov/childmentalhealth.html": ("child", "kid", "son", "daughter", "toddler"),
    "https://medlineplus.gov/olderadultmentalhealth.html": ("older", "elderly", "aging", "retire", "senior", "parent"),
    "https://medlineplus.gov/bipolardisorder.html": ("bipolar", "mania", "manic", "mood swing"),
}


def passes_topic_gate(url: str | None, user_text: str) -> bool:
    words = TOPIC_GATES.get(url or "")
    return not words or any(w in user_text.lower() for w in words)


def _to_markdown(fragment: str) -> str:
    """MedlinePlus summaries are small HTML fragments with <h3> sections, paragraphs, and lists."""
    text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n## \1\n\n", fragment, flags=re.S | re.I)
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.I)
    text = re.sub(r"</(p|ul|ol|div)>|<br\s*/?>", "\n\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def fetch_topic(term: str) -> dict | None:
    res = requests.get(API_URL, params={"db": "healthTopics", "term": term, "retmax": 1}, timeout=30)
    res.raise_for_status()
    doc = ET.fromstring(res.text).find(".//document")
    if doc is None:
        return None
    fields = {c.get("name"): "".join(c.itertext()) for c in doc.findall("content")}
    body = _to_markdown(fields.get("FullSummary", ""))
    if len(body) < 300:
        return None
    return {"url": doc.get("url"), "title": html.unescape(re.sub(r"<[^>]+>", "", fields.get("title", ""))), "body": body}


def import_medlineplus(terms=SEARCH_TERMS, pause: float = 1.0) -> list[KnowledgeArticle]:
    """Create or refresh one article per search term (its best-matching health topic)."""
    imported = []
    for term in terms:
        try:
            topic = fetch_topic(term)
        except (requests.RequestException, ET.ParseError):
            logger.warning("MedlinePlus lookup failed for %r", term, exc_info=True)
            continue
        if topic:
            article, _ = KnowledgeArticle.objects.update_or_create(
                url=topic["url"], defaults={"title": topic["title"], "body": topic["body"], "source": SOURCE}
            )
            imported.append(article)
        time.sleep(pause)  # stay well under the 85 requests/minute limit
    return imported
