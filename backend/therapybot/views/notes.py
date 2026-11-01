"""Session notes: upload, plain-language explanation, and discussing them in chat."""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from therapybot import ai
from therapybot.documents import extract_text
from therapybot.models import (
    Conversation,
    ClinicalDocument,
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
    """Text from a client's uploaded notes (PDF, Word or text). Raises ValueError with a message to show."""
    return extract_text(upload, max_bytes=5 * 1024 * 1024, max_pages=30)


class SessionNoteListCreate(generics.ListCreateAPIView):
    permission_classes = VERIFIED

    def get_queryset(self):
        return ClinicalDocument.objects.filter(owner=self.request.user, doc_type=ClinicalDocument.DocType.CLIENT_UPLOAD)

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
        note = serializer.save(
            owner=request.user, author=request.user, text=text, explanation=explanation,
            doc_type=ClinicalDocument.DocType.CLIENT_UPLOAD,
        )
        return Response(SessionNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class SessionNoteDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SessionNoteSerializer
    permission_classes = VERIFIED

    def get_queryset(self):
        return ClinicalDocument.objects.filter(owner=self.request.user, doc_type=ClinicalDocument.DocType.CLIENT_UPLOAD)


@api_view(["POST"])
@permission_classes(VERIFIED)
def discuss_note(request, pk):
    """Start a conversation that has these notes in context."""
    note = get_object_or_404(
        ClinicalDocument, pk=pk, owner=request.user, doc_type=ClinicalDocument.DocType.CLIENT_UPLOAD
    )
    conversation = Conversation.objects.create(
        user=request.user, note=note, title=f"About: {note.title}"[:120], therapy_type="General Therapy"
    )
    return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)
