"""
The therapist's work on one client's record: sessions, notes (draft → sign → addenda), homework, and the AI
assistant (prep, ask the record, note and treatment-plan drafts). Every view authorizes through
permissions.authorize_client first; AI drafts are always saved as drafts for the therapist to sign.
"""

import logging

from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from therapybot import audit, between_sessions
from therapybot.clinical import assistant, importing
from therapybot.documents import UnreadableFile, extract_text
from therapybot.models import ClinicalDocument, Plan, Session, TreatmentPlan
from therapybot.permissions import active_relationship, authorize_client
from therapybot.serializers import (
    ClinicalDocumentSerializer,
    DocumentSummarySerializer,
    ImportedDocumentSerializer,
    PlanSerializer,
    SessionSerializer,
    TreatmentPlanSerializer,
    save_goals,
)
from therapybot.views.common import ChatThrottle
from therapybot.views.practice import THERAPIST

logger = logging.getLogger(__name__)

AI_UNAVAILABLE = {"detail": "The assistant couldn't finish this right now. Please try again in a moment."}


def _document(client, doc_id) -> ClinicalDocument:
    """A document in this client's record: the practice's documents, plus the client's own uploads."""
    scope = Q(client=client)
    if client.user_id:
        scope |= Q(owner_id=client.user_id, doc_type=ClinicalDocument.DocType.CLIENT_UPLOAD)
    doc = ClinicalDocument.objects.filter(scope, pk=doc_id).select_related("author", "signed_by").first()
    if doc is None:
        raise Http404("Document not found")
    return doc


def _session(client, session_id):
    if session_id in (None, ""):
        return None
    session = Session.objects.filter(client=client, pk=session_id).first()
    if session is None:
        raise Http404("Session not found")
    return session


# --- The record ------------------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes(THERAPIST)
def timeline(request, pk):
    """Sessions (newest first) with their documents, plus documents not tied to a session."""
    client = authorize_client(request.user, pk, "record.timeline", request=request)
    scope = Q(client=client)
    if client.user_id:
        scope |= Q(owner_id=client.user_id, doc_type=ClinicalDocument.DocType.CLIENT_UPLOAD)
    documents = list(ClinicalDocument.objects.filter(scope))
    sessions = []
    for session in Session.objects.filter(client=client):
        docs = [d for d in documents if d.session_id == session.pk]
        sessions.append({**SessionSerializer(session).data, "documents": DocumentSummarySerializer(docs, many=True).data})
    loose = [d for d in documents if d.session_id is None]
    return Response({"sessions": sessions, "other_documents": DocumentSummarySerializer(loose, many=True).data})


@api_view(["POST"])
@permission_classes(THERAPIST)
def create_session(request, pk):
    client = authorize_client(request.user, pk, "session.create", request=request)
    serializer = SessionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    session = serializer.save(client=client, therapist=request.user)
    audit.record(request.user, "session.create", request=request, client=client, obj=session)
    return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes(THERAPIST)
def create_document(request, pk):
    """Add a document. Progress notes start as drafts; transcripts and intake forms are source material."""
    client = authorize_client(request.user, pk, "document.create", request=request)
    serializer = ClinicalDocumentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    session = _session(client, request.data.get("session"))
    doc_type = serializer.validated_data.get("doc_type", ClinicalDocument.DocType.PROGRESS_NOTE)
    doc = serializer.save(
        client=client, author=request.user, session=session,
        session_date=serializer.validated_data.get("session_date") or (session.date if session else None),
        status=ClinicalDocument.Status.DRAFT if doc_type == ClinicalDocument.DocType.PROGRESS_NOTE
        else ClinicalDocument.Status.FINAL,
    )
    audit.record(request.user, "document.create", request=request, client=client, obj=doc, doc_type=doc_type)
    return Response(ClinicalDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes(THERAPIST)
def document_detail(request, pk, doc_id):
    client = authorize_client(request.user, pk, "document.view" if request.method == "GET" else "document.edit",
                              request=request)
    doc = _document(client, doc_id)
    if request.method == "GET":
        return Response(ClinicalDocumentSerializer(doc).data)
    if doc.status != ClinicalDocument.Status.DRAFT or doc.client_id != client.pk:
        return Response({"detail": "Signed documents can't be edited. Add an addendum instead."},
                        status=status.HTTP_409_CONFLICT)
    serializer = ClinicalDocumentSerializer(doc, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    doc = serializer.save(session=_session(client, request.data["session"]) if "session" in request.data
                          else doc.session)
    return Response(ClinicalDocumentSerializer(doc).data)


@api_view(["POST"])
@permission_classes(THERAPIST)
def sign_document(request, pk, doc_id):
    client = authorize_client(request.user, pk, "document.sign", request=request)
    doc = _document(client, doc_id)
    if doc.status != ClinicalDocument.Status.DRAFT or doc.client_id != client.pk:
        return Response({"detail": "Only draft notes can be signed."}, status=status.HTTP_409_CONFLICT)
    doc.status, doc.signed_at, doc.signed_by = ClinicalDocument.Status.FINAL, timezone.now(), request.user
    doc.save(update_fields=["status", "signed_at", "signed_by", "updated_at"])
    audit.record(request.user, "document.sign", request=request, client=client, obj=doc)
    return Response(ClinicalDocumentSerializer(doc).data)


@api_view(["POST"])
@permission_classes(THERAPIST)
def add_addendum(request, pk, doc_id):
    """Corrections to a signed note are new draft documents that amend it; the original never changes."""
    client = authorize_client(request.user, pk, "document.addendum", request=request)
    original = _document(client, doc_id)
    if original.status != ClinicalDocument.Status.FINAL or original.client_id != client.pk:
        return Response({"detail": "Addenda are for signed notes; edit the draft instead."},
                        status=status.HTTP_409_CONFLICT)
    text = str(request.data.get("text") or "").strip()
    if not text:
        return Response({"text": ["Write the addendum."]}, status=status.HTTP_400_BAD_REQUEST)
    doc = ClinicalDocument.objects.create(
        client=client, author=request.user, session=original.session, session_date=original.session_date,
        doc_type=ClinicalDocument.DocType.PROGRESS_NOTE, status=ClinicalDocument.Status.DRAFT,
        title=f"Addendum: {original.title}"[:120], text=text, amends=original,
    )
    audit.record(request.user, "document.addendum", request=request, client=client, obj=doc)
    return Response(ClinicalDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


# --- Homework --------------------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes(THERAPIST)
def homework(request, pk):
    """Plans assigned to the client. They appear in the client's own Plans and reminders."""
    client = authorize_client(request.user, pk, "homework.view" if request.method == "GET" else "homework.assign",
                              request=request)
    if request.method == "GET":
        plans = Plan.objects.filter(client=client).prefetch_related("steps__check_ins")
        return Response(PlanSerializer(plans, many=True, context={"request": request}).data)
    if client.user_id is None:
        return Response({"detail": "This client hasn't accepted your invitation yet."},
                        status=status.HTTP_400_BAD_REQUEST)
    serializer = PlanSerializer(data={**request.data, "conversation": None}, context={"request": request})
    serializer.is_valid(raise_exception=True)
    plan = serializer.save(user=client.user, client=client, assigned_by=request.user)
    audit.record(request.user, "homework.assign", request=request, client=client, obj=plan)
    return Response(PlanSerializer(plan, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes(THERAPIST)
@throttle_classes([ChatThrottle])
def between_sessions_view(request, pk):
    """The client's companion activity since the last session, limited to what they've chosen to share."""
    client = authorize_client(request.user, pk, "record.between_sessions", request=request)
    data = between_sessions.between_sessions(client, active_relationship(request.user, client))
    audit.record(request.user, "chat.shared_view", request=request, client=client,
                 conversations=len(data["conversations"]),
                 raw=any(c["messages"] is not None for c in data["conversations"]))
    return Response(data)


# --- Importing existing records ----------------------------------------------------------------------

MAX_IMPORT_FILES = 10


@api_view(["POST"])
@permission_classes(THERAPIST)
def import_preview(request, pk):
    """
    Read uploaded files (PDF, Word, text) and suggest the documents in them. Nothing is saved: the therapist
    reviews dates, types and titles, then confirms with import_records.
    """
    client = authorize_client(request.user, pk, "record.import_preview", request=request)
    uploads = request.FILES.getlist("files")
    if not uploads:
        return Response({"files": ["Choose at least one file."]}, status=status.HTTP_400_BAD_REQUEST)
    if len(uploads) > MAX_IMPORT_FILES:
        return Response({"files": [f"Upload up to {MAX_IMPORT_FILES} files at a time."]},
                        status=status.HTTP_400_BAD_REQUEST)
    files = []
    for upload in uploads:
        try:
            files.append({"filename": upload.name, "documents": importing.split_records(extract_text(upload), upload.name)})
        except UnreadableFile as e:
            files.append({"filename": upload.name, "error": str(e), "documents": []})
    audit.record(request.user, "record.import_preview", request=request, client=client, files=len(files),
                 documents=sum(len(f["documents"]) for f in files))
    return Response({"files": files})


@api_view(["POST"])
@permission_classes(THERAPIST)
def import_records(request, pk):
    """Save the documents the therapist reviewed. Dated notes are attached to (or create) that day's session."""
    client = authorize_client(request.user, pk, "record.import", request=request)
    serializer = ImportedDocumentSerializer(data=request.data.get("documents"), many=True)
    serializer.is_valid(raise_exception=True)
    if not serializer.validated_data:
        return Response({"documents": ["Nothing selected to import."]}, status=status.HTTP_400_BAD_REQUEST)
    if len(serializer.validated_data) > importing.MAX_DOCUMENTS:
        return Response({"documents": [f"Import up to {importing.MAX_DOCUMENTS} documents at a time."]},
                        status=status.HTTP_400_BAD_REQUEST)
    result = importing.import_documents(client=client, therapist=request.user, documents=serializer.validated_data)
    audit.record(request.user, "record.import", request=request, client=client,
                 documents=len(result["documents"]), sessions_created=result["sessions_created"])
    return Response({"created": len(result["documents"]), "sessions_created": result["sessions_created"]},
                    status=status.HTTP_201_CREATED)


# --- AI assistant ------------------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes(THERAPIST)
@throttle_classes([ChatThrottle])
def prep(request, pk):
    client = authorize_client(request.user, pk, "record.prep", request=request)
    try:
        return Response(assistant.session_prep(actor=request.user, client=client, request=request))
    except Exception:
        logger.exception("Session prep failed for client %s", client.pk)
        return Response(AI_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(["POST"])
@permission_classes(THERAPIST)
@throttle_classes([ChatThrottle])
def ask(request, pk):
    client = authorize_client(request.user, pk, "record.ask", request=request)
    question = str(request.data.get("question") or "").strip()
    if not question:
        return Response({"question": ["Ask a question about this client's record."]}, status=400)
    try:
        return Response(assistant.ask_record(actor=request.user, client=client, question=question[:1000],
                                             request=request))
    except Exception:
        logger.exception("Ask-the-record failed for client %s", client.pk)
        return Response(AI_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(["POST"])
@permission_classes(THERAPIST)
@throttle_classes([ChatThrottle])
def draft_note(request, pk):
    """Draft a SOAP/DAP note from a transcript or rough notes; saved as a draft (and the source, optionally)."""
    client = authorize_client(request.user, pk, "document.draft", request=request)
    source_text = str(request.data.get("source_text") or "").strip()
    if len(source_text) < 40:
        return Response({"source_text": ["Paste the transcript or your rough notes."]}, status=400)
    if len(source_text) > 20000:
        return Response({"source_text": ["Keep the source under 20,000 characters."]}, status=400)
    session = _session(client, request.data.get("session"))
    note_format = request.data.get("format") or request.user.profile.note_format
    try:
        draft = assistant.draft_progress_note(actor=request.user, client=client, source_text=source_text,
                                              note_format=note_format, request=request)
    except Exception:
        logger.exception("Note draft failed for client %s", client.pk)
        return Response(AI_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    session_date = session.date if session else timezone.localdate()
    with transaction.atomic():
        if request.data.get("save_transcript", True):
            ClinicalDocument.objects.create(
                client=client, author=request.user, session=session, session_date=session_date,
                doc_type=ClinicalDocument.DocType.TRANSCRIPT, status=ClinicalDocument.Status.FINAL,
                title=f"Transcript {session_date:%b %d, %Y}", text=source_text,
            )
        doc = ClinicalDocument.objects.create(
            client=client, author=request.user, session=session, session_date=session_date,
            doc_type=ClinicalDocument.DocType.PROGRESS_NOTE, status=ClinicalDocument.Status.DRAFT,
            title=f"{draft['format'].upper()} note {session_date:%b %d, %Y} (AI draft)",
            text=assistant.render_note(draft["format"], draft["sections"]),
        )
    return Response({"document": ClinicalDocumentSerializer(doc).data, "review_flags": draft["review_flags"]},
                    status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes(THERAPIST)
def treatment_plans(request, pk):
    """GET: the client's treatment plans. POST {modality}: AI-draft a new plan from the record (saved as draft)."""
    client = authorize_client(request.user, pk, "treatment_plan.view" if request.method == "GET"
                              else "treatment_plan.draft", request=request)
    if request.method == "GET":
        plans = TreatmentPlan.objects.filter(client=client).prefetch_related("goals__objectives")
        return Response(TreatmentPlanSerializer(plans, many=True).data)
    modality = request.data.get("modality") or Session.Modality.INTEGRATIVE
    if modality not in Session.Modality.values:
        return Response({"modality": ["Choose CBT, DBT, ACT, or Integrative."]}, status=400)
    try:
        draft = assistant.draft_treatment_plan(actor=request.user, client=client,
                                               modality_label=Session.Modality(modality).label, request=request)
    except Exception:
        logger.exception("Treatment plan draft failed for client %s", client.pk)
        return Response(AI_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if not draft["goals"]:
        return Response({"detail": "There isn't enough in the record yet to draft a plan. Add session notes first."},
                        status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        plan = TreatmentPlan.objects.create(client=client, therapist=request.user, modality=modality,
                                            problem_summary=draft["problem_summary"], ai_generated=True)
        save_goals(plan, [{**g, "evidence": assistant.evidence_for(g["sources"], draft["sources"])}
                          for g in draft["goals"]])
    return Response({**TreatmentPlanSerializer(plan).data, "sources": draft["sources"]},
                    status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(THERAPIST)
def treatment_plan_detail(request, pk, plan_id):
    client = authorize_client(request.user, pk, "treatment_plan.edit", request=request)
    plan = TreatmentPlan.objects.filter(client=client, pk=plan_id).first()
    if plan is None:
        raise Http404("Treatment plan not found")
    if plan.status != TreatmentPlan.Status.DRAFT:
        return Response({"detail": "Active plans can't be edited; draft a new version."}, status=409)
    serializer = TreatmentPlanSerializer(plan, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    return Response(TreatmentPlanSerializer(serializer.save()).data)


@api_view(["POST"])
@permission_classes(THERAPIST)
def sign_treatment_plan(request, pk, plan_id):
    """The signed plan becomes the client's active plan; any previous active plan is archived."""
    client = authorize_client(request.user, pk, "treatment_plan.sign", request=request)
    plan = TreatmentPlan.objects.filter(client=client, pk=plan_id, status=TreatmentPlan.Status.DRAFT).first()
    if plan is None:
        raise Http404("Draft treatment plan not found")
    with transaction.atomic():
        TreatmentPlan.objects.filter(client=client, status=TreatmentPlan.Status.ACTIVE).update(
            status=TreatmentPlan.Status.ARCHIVED
        )
        plan.status, plan.signed_at = TreatmentPlan.Status.ACTIVE, timezone.now()
        plan.save(update_fields=["status", "signed_at", "updated_at"])
    audit.record(request.user, "treatment_plan.sign", request=request, client=client, obj=plan)
    return Response(TreatmentPlanSerializer(plan).data)
