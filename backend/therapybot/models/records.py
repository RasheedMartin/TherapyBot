"""Clinical documents."""

from django.conf import settings
from django.db import models


class SessionNote(models.Model):
    """Notes or an after-visit summary from the user's own clinician, with a plain-language explanation."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_notes")
    title = models.CharField(max_length=120)
    session_date = models.DateField(null=True, blank=True)
    original_text = models.TextField(max_length=20000)
    # {"summary", "key_points": [...], "terms": [{"term", "meaning"}], "homework": [...steps], "questions": [...]}
    explanation = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-session_date", "-created_at"]

    def __str__(self):
        return self.title

    def chat_context(self) -> str:
        """The notes' explanation, for a conversation started from them."""
        e = self.explanation or {}
        lines = [f"\nThis conversation is about notes from their clinician ({self.title}). Plain-language summary:",
                 e.get("summary", "")]
        if e.get("homework"):
            lines.append("Assigned homework: " + "; ".join(h["title"] for h in e["homework"]))
        lines.append("Help them understand and act on these notes. Don't contradict their clinician; "
                     "suggest they ask their clinician about anything uncertain.")
        return "\n".join(lines)
