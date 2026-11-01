# TherapyBot refactor brief: from patient chatbot to therapist workflow layer

Read this whole brief, then explore the repo before changing anything. Start by producing a written plan (phases, files touched, migrations, open questions) and **stop for my approval** before writing code.

## Why we're changing direction

TherapyBot today is a patient-facing support chatbot: a user signs up, chats with a RAG bot grounded in public mental-health articles, builds plans, uploads session notes for explanation, and finds providers. That puts it in a crowded space next to BetterHelp and Talkspace, which sell access to licensed therapists.

The new direction: **TherapyBot is an AI workflow layer for therapists.** It doesn't replace the therapist or compete with marketplaces. It turns each client's session notes, transcripts, screenings, and treatment plan into a secure, searchable memory, then uses that memory to help the therapist prep for sessions, track progress, and draft documentation and treatment plans. Every AI output cites the session it came from. Between appointments, the client gets support tied directly to their therapist's plan and assigned exercises, not generic content.

The core shift in the RAG: the retrieval corpus moves from "public therapy articles for everyone" to **"this client's own clinical record,"** with the existing curated knowledge base kept as a secondary reference layer (protocols, screening instruments, modality guidance).

## What exists today (verify as you explore)

- `backend/` — Django 5.2 + DRF, SimpleJWT, Postgres via `dj-database-url`, deployed on Railway (Dockerfile, `railway*.toml`).
- `backend/therapybot/ai.py` — LlamaIndex 0.14, FastEmbed local embeddings, Groq LLMs (`GROQ_MODEL`, `GROQ_FAST_MODEL`). One global `VectorStoreIndex` built from `knowledge/*.md` + `KnowledgeArticle` rows, persisted as JSON in `backend/storage/`. Also: `is_crisis_message` regex + `assess_risk` LLM screener (none/elevated/imminent), `therapy_chat` / `therapy_chat_stream`, `summarize_conversation`, `draft_plan`, `explain_notes`.
- `models.py` — `Profile`, `Conversation`, `Message` (with `risk_level`, `sources`), `Plan` / `PlanStep` / `StepCheckIn`, `SavedProvider`, `KnowledgeArticle`, `SessionNote`. Everything is owned by a single `user`; there is no therapist role.
- `views.py` / `urls.py` — auth, conversations + streaming, plans + calendar feed, reminders, provider search (NPI), notes.
- `evals/` — `run_evals` management command with hard checks + judge-model rubric. `tests.py` has API and safety tests with the AI mocked.
- `frontend/` — React + TypeScript + MUI (Vite, Vercel). Pages: Home, Dashboard, Chat, Plans, Notes, FindCare, Profile.

## Target product

**Therapist side (primary user)**
1. **Client roster.** A therapist sees their clients, invites a client by email, and links an existing patient account.
2. **Client record.** Per-client session notes (typed or uploaded PDF/text), optional transcripts, screening results, and a treatment plan.
3. **Session prep.** "What did we work on last time, what's still open, what homework was assigned, did they do it?" Answered from the client's record, with citations to specific sessions.
4. **Progress tracking.** Screening scores over time (PHQ-9, GAD-7 to start) plus recurring themes across sessions.
5. **Documentation drafts.** Generate a draft progress note (SOAP or DAP) from a transcript or rough notes. The therapist always reviews and edits. Nothing is finalized automatically.
6. **Treatment plan drafting.** Goals, objectives, and interventions pulled from session evidence and mapped to a modality. Reuse the existing `Plan` / `PlanStep` structure where it fits.
7. **Ask the record.** A free-form Q&A over one client's history, scoped strictly to that client.

**Client side (secondary)**
- Keep chat, plans, check-ins, reminders, and crisis handling, but when a client is linked to a therapist, ground the companion in **that therapist's plan and assigned exercises**, not only the general knowledge base.
- Client check-in data and between-session chat summaries flow back into the therapist's view (with the client's consent).
- Unlinked users can keep today's experience, but it's no longer the focus. Don't delete it unless the plan justifies that.

## RAG architecture

- **Two corpora:**
  - `client_record` — per-client chunks from notes, transcripts, screenings, and plans. Metadata on every chunk: `client_id`, `practice_id`, `session_id`, `session_date`, `doc_type`, `author`.
  - `clinical_reference` — the existing knowledge base, re-scoped to protocols, screening instruments, and modality guidance.
- **Tenant isolation is the top requirement.** Every retrieval against `client_record` must be filtered by `client_id`, enforced in one choke-point function that cannot be called without it, plus a check that the requesting therapist is authorized for that client. Write tests proving client A's data never appears in client B's results, including adversarial queries.
- **Vector store:** the JSON on-disk store can't support per-client, frequently updated data. Propose a replacement (my lean is pgvector, since we're already on Postgres) and justify it in the plan.
- **Incremental indexing:** creating or editing a note re-indexes only that document, not the whole store.
- **Citations everywhere:** therapist-facing outputs return structured sources (session id, date, snippet) so the UI can link each claim back to its session. Extend the existing `Message.sources` pattern.

## Data model changes (propose specifics in the plan)

- Roles: therapist vs client (and maybe a practice admin later).
- `Practice`, a therapist ↔ client relationship with status and consent timestamp, `Session` (date, modality, linked notes and transcript), `Screening` (instrument, item responses, total score, date), and a structured treatment plan tied to a client and therapist.
- Generalize `SessionNote` from "patient uploads their notes" to "clinical document in a client's record." Write migrations that preserve existing data.
- An audit log of who accessed or generated what, for which client, and when.

## Safety, privacy, compliance

- Keep and reuse the crisis pipeline (`is_crisis_message`, `assess_risk`). When a linked client's risk is elevated or imminent, the therapist gets a flag in their dashboard. Never weaken existing crisis responses or their tests.
- Assume this will eventually hold PHI. Design for HIPAA-grade handling now: least-privilege access, audit logging, no PHI in logs or eval fixtures, and encryption at rest for sensitive fields where practical.
- **LLM provider abstraction:** Groq is fine for the demo, but put LLM and embedding calls behind an interface so we can switch to a provider that will sign a BAA. Flag in the plan which features send client data to an external model.
- Use only synthetic data in seeds, tests, and evals. Add a seed command that creates a demo practice, therapist, and a few synthetic clients with several sessions each.
- AI drafts are labeled as drafts and require therapist sign-off.

## Evals

Extend `evals/` with therapist-side cases: session-prep accuracy against a synthetic record, citation correctness (every claim traceable to a real chunk), no hallucinated sessions or scores, SOAP/DAP draft quality, and cross-client leakage checks. Keep the existing patient-side cases passing.

## Frontend

- A therapist app shell: client roster → client detail (timeline of sessions, screenings chart, treatment plan, "prep for next session" panel, ask-the-record box with clickable citations) → note editor with "draft from transcript."
- Route by role. Reuse existing MUI components and the theme.

## Constraints and working style

- Phase the work so each phase ends in a working, tested state. Suggested order: (1) roles + practice/client models + permissions, (2) vector store migration + per-client indexing + isolation tests, (3) therapist API endpoints (prep, ask-the-record, documentation and plan drafts) with citations, (4) screenings, (5) therapist frontend, (6) client companion grounded in the therapist's plan, (7) evals + seed data + README update.
- Keep `tests.py` green and add tests alongside each phase. Mock the LLM in unit tests.
- Don't touch deployment config beyond what new dependencies require, and call those changes out.
- Prefer small, readable modules over growing `ai.py` and `views.py` further. Splitting them is in scope.
- When a decision is ambiguous, list it as an open question in the plan instead of guessing.
