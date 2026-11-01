"""Importing a therapist's existing records: reading files, splitting exports into notes, saving them."""

import io
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from therapybot.clinical.importing import find_date, guess_type, split_records
from therapybot.models import AuditEvent, ClinicalDocument, Session
from therapybot.tests.helpers import APITestCase

BODY = "Client reported improved sleep and used paced breathing before meetings. " * 3

EXPORT = f"""Practice export for Sam Rivera
DOB: 04/02/1985

Progress Note
Date of Service: 03/14/2026
Subjective: {BODY}
Plan: continue graded exposure.

Progress Note
Date of Service: 2026-03-21
Subjective: {BODY}
Plan: begin stimulus control.

Intake Assessment - March 7, 2026
Presenting problem: panic attacks on the subway. {BODY}
"""


def docx_bytes(paragraphs):
    from docx import Document

    document = Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class SplitRecordsTests(APITestCase):
    def test_export_splits_into_dated_typed_notes_and_skips_birth_dates(self):
        docs = split_records(EXPORT, "export.pdf")
        self.assertEqual([(d["doc_type"], d["session_date"]) for d in docs], [
            ("progress_note", "2026-03-14"),
            ("progress_note", "2026-03-21"),
            ("intake", "2026-03-07"),
        ])
        self.assertIn("Sam Rivera", docs[0]["text"])  # the short cover page stays with the first note
        self.assertNotIn("Date of Service: 2026-03-21", docs[0]["text"])

    def test_single_note_is_one_document(self):
        docs = split_records(f"Session note 2026-02-01\n{BODY}", "note.txt")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["session_date"], "2026-02-01")

    def test_dates_and_types(self):
        self.assertIsNone(find_date("DOB: 01/02/1990"))
        future = (timezone.localdate() + timedelta(days=30)).isoformat()
        self.assertIsNone(find_date(f"Next appointment {future}"))  # notes can't be from the future
        self.assertEqual(find_date("Seen on 14 March 2026"), date(2026, 3, 14))
        transcript = "\n".join(["T: How was the week?", "C: Better.", "T: What helped?", "C: Walking."])
        self.assertEqual(guess_type(transcript), "transcript")

    def test_oversized_note_is_split_into_parts(self):
        docs = split_records("Progress note 2026-01-05\n" + ("word " * 2000 + "\n\n") * 3, "big.txt")
        self.assertGreater(len(docs), 1)
        self.assertTrue(all(len(d["text"]) <= 20000 for d in docs))
        self.assertIn("(part 1 of", docs[0]["title"])


class ImportApiTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.therapist = self.make_therapist()
        self.client_record, _ = self.link(self.therapist, self.make_user())
        self.base = f"/api/practice/clients/{self.client_record.pk}/import"
        self.login(self.therapist)

    def test_preview_reads_word_and_text_and_reports_unreadable_files(self):
        files = [
            SimpleUploadedFile("notes.docx", docx_bytes(EXPORT.splitlines())),
            SimpleUploadedFile("note.txt", f"Session note 2026-02-01\n{BODY}".encode()),
            SimpleUploadedFile("scan.pdf", b"%PDF-1.4 not really a pdf"),
            SimpleUploadedFile("old.doc", b"binary"),
        ]
        res = self.client.post(f"{self.base}/preview/", {"files": files}, format="multipart")
        self.assertEqual(res.status_code, 200)
        by_name = {f["filename"]: f for f in res.data["files"]}
        self.assertEqual(len(by_name["notes.docx"]["documents"]), 3)
        self.assertEqual(len(by_name["note.txt"]["documents"]), 1)
        self.assertIn("error", by_name["scan.pdf"])
        self.assertIn(".docx", by_name["old.doc"]["error"])
        self.assertFalse(ClinicalDocument.objects.exists())  # preview never saves

    def test_import_saves_final_documents_and_attaches_sessions(self):
        existing = Session.objects.create(client=self.client_record, therapist=self.therapist, date=date(2026, 3, 14))
        docs = [
            {"title": "Progress Note", "doc_type": "progress_note", "session_date": "2026-03-14", "text": BODY,
             "filename": "export.pdf"},
            {"title": "Progress Note", "doc_type": "progress_note", "session_date": "2026-03-21", "text": BODY,
             "filename": "export.pdf"},
            {"title": "Referral letter", "doc_type": "other", "session_date": None, "text": BODY},
        ]
        res = self.client.post(f"{self.base}/", {"documents": docs}, format="json")
        self.assertEqual((res.status_code, res.data), (201, {"created": 3, "sessions_created": 1}))
        imported = ClinicalDocument.objects.filter(client=self.client_record).order_by("session_date", "id")
        self.assertTrue(all(d.status == "final" for d in imported))
        self.assertEqual(imported.get(session_date=date(2026, 3, 14)).session, existing)
        self.assertEqual(imported.get(session_date=date(2026, 3, 21)).session.status, "completed")
        self.assertIsNone(imported.get(doc_type="other").session)
        self.assertEqual(imported.first().imported_from, "export.pdf")
        self.assertTrue(AuditEvent.objects.filter(action="record.import").exists())

    def test_validation_and_access(self):
        future = (timezone.localdate() + timedelta(days=3)).isoformat()
        bad = [{"title": "x", "doc_type": "client_upload", "session_date": future, "text": "short"}]
        res = self.client.post(f"{self.base}/", {"documents": bad}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(set(res.data[0]), {"doc_type", "session_date", "text"})

        self.login(self.make_therapist("drkim", "drkim@example.com"))
        res = self.client.post(f"{self.base}/", {"documents": [{"title": "x", "doc_type": "other", "text": BODY}]},
                               format="json")
        self.assertEqual(res.status_code, 404)
        self.assertFalse(ClinicalDocument.objects.exists())
