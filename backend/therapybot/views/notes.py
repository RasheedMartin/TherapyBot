"""Session notes: upload, plain-language explanation, and discussing them in chat."""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from therapybot import ai
from therapybot.models import (
    Conversation,
    SessionNote,
)
from therapybot.serializers import (
    ConversationSerializer,
    SessionNoteListSerializer,
    SessionNoteSerializer,
)
from therapybot.views.common import VERIFIED, ChatThrottle, get_profile
from therapybot.views.plans import clean_ai_steps

logger = logging.getLogger(__name__)


MAX_NOTE_CHARS = 20000


def _extract_upload_text(upload) -> str:
    name = (upload.name or "").lower()
    if upload.size > 5 * 1024 * 1024:
        raise ValueError("That file is too large. Please upload a file under 5 MB.")
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(upload)
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:30])
        except (PdfReadError, ValueError):
            raise ValueError("Couldn't read that PDF. Try copying and pasting the text instead.")
        if len(text.strip()) < 20:
            raise ValueError("That PDF looks like a scanned image, so there's no text to read. Please paste the text.")
        return text
    if name.endswith((".txt", ".md")):
        return upload.read().decode("utf-8", errors="replace")
    raise ValueError("Upload a PDF or text file, or paste your notes.")


class SessionNoteListCreate(generics.ListCreateAPIView):
    permission_classes = VERIFIED

    def get_queryset(self):
        return SessionNote.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return SessionNoteListSerializer if self.request.method == "GET" else SessionNoteSerializer

    def get_throttles(self):
        return [ChatThrottle()] if self.request.method == "POST" else super().get_throttles()

    def create(self, request, *args, **kwargs):
        try:
            upload = request.FILES.get("file")
            text = _extract_upload_text(upload) if upload else (request.data.get("text") or "")
        except ValueError as e:
            return Response({"file": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        text = text.strip()
        if len(text) < 20:
            return Response({"text": ["Paste or upload your notes (at least a sentence or two)."]}, status=400)
        if len(text) > MAX_NOTE_CHARS:
            return Response({"text": [f"Notes are limited to {MAX_NOTE_CHARS:,} characters."]}, status=400)

        try:
            raw = ai.explain_notes(text, get_profile(request.user).chat_context())
        except Exception:
            logger.exception("Notes explanation failed for user %s", request.user.pk)
            return Response({"detail": "Couldn't explain these notes right now. Please try again."}, status=503)

        explanation = {
            "summary": str(raw.get("summary", ""))[:2000],
            "key_points": [str(p)[:500] for p in raw.get("key_points", []) if p][:8],
            "terms": [
                {"term": str(t.get("term", ""))[:80], "meaning": str(t.get("meaning", ""))[:500]}
                for t in raw.get("terms", [])
                if isinstance(t, dict) and t.get("term")
            ][:12],
            "homework": clean_ai_steps(raw.get("homework"), limit=8),
            "questions": [str(q)[:300] for q in raw.get("questions", []) if q][:6],
        }
        serializer = SessionNoteSerializer(data={
            "title": (request.data.get("title") or raw.get("title") or "Session notes")[:120],
            "session_date": request.data.get("session_date") or None,
        })
        serializer.is_valid(raise_exception=True)
        note = serializer.save(user=request.user, original_text=text, explanation=explanation)
        return Response(SessionNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class SessionNoteDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionNoteSerializer
    permission_classes = VERIFIED

    def get_queryset(self):
        return SessionNote.objects.filter(user=self.request.user)


@api_view(["POST"])
@permission_classes(VERIFIED)
def discuss_note(request, pk):
    """Start a conversation that has these notes in context."""
    note = get_object_or_404(SessionNote, pk=pk, user=request.user)
    conversation = Conversation.objects.create(
        user=request.user, note=note, title=f"About: {note.title}"[:120], therapy_type="General Therapy"
    )
    return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)
