# TherapyBot 🧠💬

An AI workflow layer for therapists, and a companion for their clients between sessions. Therapists get a
searchable, cited memory of each client's record; clients get support that follows the plan they made with
their therapist. People without a therapist can still use the companion on its own and find care nearby.

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Django](https://img.shields.io/badge/Django-5.2-green.svg)
![React](https://img.shields.io/badge/React-19-61DAFB.svg)
![Postgres](https://img.shields.io/badge/Postgres-17%20%2B%20pgvector-336791.svg)

> **Synthetic data only.** This is a concept build. Real client data needs HIPAA-eligible hosting and business
> associate agreements with every provider that touches it (hosting, LLM, email). Until then `PHI_ALLOWED`
> stays `false` and the therapist app shows a synthetic-data banner.

## 🌟 Features

**For therapists** (`/practice`, NPI-verified accounts)

- **Session prep:** where things stand, last session, open threads, homework completion and score trends,
  with every point cited to the note (or shared chat summary) it came from
- **Ask the record:** questions answered only from the client's record, with citations; "I couldn't find
  that" when the record doesn't say
- **Notes:** SOAP or DAP drafts from a transcript or rough notes, with review flags (e.g. risk content). The
  therapist edits and signs; signed notes are locked and corrected only by addenda
- **Treatment plans:** CBT / DBT / ACT / integrative drafts (goals → objectives → interventions), each goal cited
- **Screenings:** PHQ-9 and GAD-7, scored in code, charted over time; item 9 raises a safety flag
- **Between sessions:** summaries of the companion conversations a client chooses to share, check-in
  completion, and safety flags from chat, with an emailed alert (no clinical content in the email)

**For clients**

- A conversational companion grounded in vetted articles and, when linked, their therapist's plan and homework
- Plans and daily routines with reminders and calendar sync; homework from the therapist appears here
- Plain-language explanations of their therapist's notes, and a map-based therapist finder (NPI Registry)
- Control over sharing: what each therapist sees, conversation by conversation, changeable any time.
  Safety flags are always shared (disclosed up front) and are not live monitoring

**Safety and privacy**

- Every client-scoped read goes through one authorization point (`permissions.authorize_client`) and the
  retrieval choke point (`rag.search_client_record`), which filter by client in SQL and are audited
- Clinical text is encrypted at rest (Fernet, `FIELD_ENCRYPTION_KEYS`); the audit log is append-only
- AI output is validated server-side: citations to sources that weren't supplied are removed, uncited claims
  are dropped, and prep warns when it describes risk as absent without a documented assessment

## 🏗️ Architecture

```
backend/
├── djangoProject/            settings, URLs
├── therapybot/
│   ├── models/               accounts, companion, practice (clients, care relationships, audit), records, rag
│   ├── views/                REST API by area (chat, plans, care, practice, clinical, screenings, care_team)
│   ├── permissions.py        who may see which client (single authorization point, audited)
│   ├── llm/                  provider abstraction: Groq chat models, local FastEmbed embeddings
│   ├── rag/                  chunking, indexing (pgvector), hybrid retrieval (vector + BM25, RRF)
│   ├── ai/                   client companion: chat, plan and notes drafting, prompts
│   ├── clinical/             therapist AI: prep, ask, note and treatment-plan drafts, citations, screenings
│   ├── between_sessions.py   companion ↔ care team: plan context, chat risk flags, shared summaries
│   ├── safety.py             crisis detection and risk screening
│   └── tests/                API, isolation, clinical and safety tests (AI mocked)
├── evals/                    real-model evals: companion (cases.json) and therapist side (clinical.json)
└── knowledge/                skill guides for the companion (plus imported MedlinePlus articles)
frontend/src/
├── pages/                    client pages, practice/ (therapist app), landing
├── components/               chat/, plans/, care/, practice/ (prep, ask, citations, screenings, ...)
└── api/                      Axios client with token refresh, shared types
```

## 🚀 Local Development

### Prerequisites

- Python 3.13
- PostgreSQL 17 with the pgvector extension (client records are searched in the database; SQLite won't work)
- Node.js 20+
- [Groq API key](https://console.groq.com) (free tier works for development)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install postgresql@17 pgvector && brew services start postgresql@17 && createdb therapybot
cp .env.example .env            # fill in GROQ_API_KEY, SECRET_KEY and DATABASE_URL
python manage.py migrate
python manage.py seed_demo      # optional: synthetic practice (demo_therapist / demo_jordan / ...)
python manage.py runserver      # http://localhost:8000
```

On macOS, if Python exits immediately at launch (killed by the system, exit code 137), the interpreter
install is the problem rather than the project; Anaconda's has done this. Create the venv with the python.org
build instead: `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m venv .venv`.

Run the tests with `python manage.py test`. After changing prompts, models or retrieval, run the evals
against the real models (see `backend/evals/README.md`):

```bash
python manage.py run_evals                 # client companion: tone, safety, risk screening
python manage.py run_clinical_evals        # therapist side: citations, invented facts, cross-client leakage
```

The companion's reference material is MedlinePlus articles (imported with `python manage.py import_articles`,
editable in the admin) plus the skill guides in `backend/knowledge/` (each needs clinical review before
production). Embeddings run locally (FastEmbed, `bge-small-en-v1.5`), so no embedding API key is needed; the
model (~70 MB) downloads on first use. `python manage.py reindex` rebuilds the vectors for client records.

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5174
```

In development, `/api` requests are proxied to `localhost:8000`, so no frontend env vars are needed.
If port 8000 is taken, run Django on another port (`python manage.py runserver 8001`) and create
`frontend/.env.local` containing `API_PROXY_TARGET=http://localhost:8001`.

## ☁️ Deployment

### Backend — Railway (Docker)

Set the service root to `backend/`. The container runs migrations, then serves with gunicorn on `$PORT`.
Use `/api/health/` as the health-check path.

| Variable                                                                     | Required | Description                                                           |
| ---------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------- |
| `SECRET_KEY`                                                                 | ✅       | Long random string                                                    |
| `GROQ_API_KEY`                                                               | ✅       | Groq API key                                                          |
| `FRONTEND_URL`                                                               | ✅       | Vercel URL, e.g. `https://therapybot.vercel.app` (CORS + reset links) |
| `DATABASE_URL`                                                               | ✅       | Railway Postgres (pgvector is enabled by the migrations)              |
| `FIELD_ENCRYPTION_KEYS`                                                      |          | Comma-separated Fernet keys for clinical text (newest first). Derived from `SECRET_KEY` if unset, so never rotate `SECRET_KEY` without setting this first |
| `PHI_ALLOWED`                                                                |          | `false` (default) until HIPAA hosting and BAAs are in place; requires `FIELD_ENCRYPTION_KEYS` when `true` |
| `ALLOWED_HOSTS`                                                              |          | Extra hostnames; the Railway domain is added automatically            |
| `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`                                       |          | Email (verification, reset, invite, reminder, safety-flag) via Resend's HTTP API; the from-address domain must be verified in Resend. Railway blocks SMTP on the Hobby plan, so prefer this |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`                       |          | SMTP instead of Resend's API (used only when `RESEND_API_KEY` is unset). Emails are printed to logs if neither is set |
| `GOOGLE_CLIENT_ID`    |          | Enables "Continue with Google" (Web OAuth client ID) |
| `GROQ_FAST_MODEL`     |          | Model for risk screening, next-step detection and summaries (default `openai/gpt-oss-20b`) |
| `THROTTLE_CHAT`                                                              |          | Per-user chat rate limit (default `20/min`)                           |
| `WEB_CONCURRENCY`                                                            |          | Gunicorn workers (default 2)                                          |

Create an admin user with `railway run python manage.py createsuperuser`; the admin lives at `/admin/`.

> **Capacity:** Groq's free tier allows about 8,000 tokens per minute per model, which is roughly 3 chat
> replies per minute across *all* users. Upgrade to Groq's Developer tier before launch.

**One-time setup and scheduled jobs on Railway:**

| Command | When | What it does |
| ------- | ---- | ------------ |
| `python manage.py import_articles` | Once after first deploy, then weekly (cron `0 6 * * 1`) | Imports MedlinePlus mental-health articles into the database and rebuilds the retrieval index |
| `python manage.py send_reminders` | Every 15 minutes (cron `*/15 * * * *`) | Sends daily plan reminder emails that are due in each user's time zone |

Create each as a Railway cron service using the same Docker image and environment variables. The web service
rebuilds the retrieval index on start only when its content has changed (`build_index --if-stale`).
Reminder emails need SMTP configured (`EMAIL_HOST`, ...) and `API_BASE_URL` set if the API isn't on the Railway domain.

### Frontend — Vercel

Set the project root to `frontend/` and add `VITE_API_URL` = your Railway backend URL (no trailing slash).

## 📊 API

All endpoints are under `/api/`. Except where noted, they require `Authorization: Bearer <access token>`.

| Method           | Path                           | Description                                      |
| ---------------- | ------------------------------ | ------------------------------------------------ |
| POST             | `token/` _(public)_            | Log in → `{access, refresh}`                     |
| POST             | `token/refresh/` _(public)_    | Rotate tokens                                    |
| POST             | `token/logout/` _(public)_     | Revoke a refresh token                           |
| POST             | `register/` _(public)_         | Create an account                                |
| POST             | `forgot-password/` _(public)_  | Email a reset link                               |
| POST             | `reset-password/` _(public)_   | `{uid, token, new_password}`                     |
| GET              | `health/` _(public)_           | Liveness + database check                        |
| GET              | `current_user/`                | Signed-in user                                   |
| GET/PATCH        | `profile/`                     | Profile and care preferences                     |
| POST             | `account/password/`            | Change password                                  |
| GET              | `account/export/`              | Download all of the user's data (JSON)           |
| POST             | `account/delete/`              | `{password}`; permanently deletes the account    |
| GET/POST         | `conversations/`               | List / create (`{therapy_type}`)                 |
| GET/PATCH/DELETE | `conversations/<id>/`          | Conversation with messages / rename / delete     |
| POST             | `conversations/<id>/messages/` | `{content}` → saves the message and the AI reply |
| POST             | `conversations/<id>/messages/stream/` | Same, streamed as newline-delimited JSON  |
| GET              | `config/` _(public)_           | Public settings (Google client ID)               |
| POST             | `auth/google/` _(public)_      | Google ID token → JWTs (new users send consent) |
| POST             | `verify-email/` _(public)_     | `{uid, token}` from the verification email      |
| POST             | `verify-email/resend/`         | Send a new verification link                     |
| GET              | `providers/?zip=&types=`       | Licensed providers near a ZIP (NPI Registry)     |
| GET/POST         | `saved-providers/`             | Shortlist                                        |
| PATCH/DELETE     | `saved-providers/<id>/`        | Outreach status / notes / remove                 |
| GET/POST         | `plans/`                       | Plans with steps                                 |
| POST             | `plans/draft/`                 | `{conversation}` → AI-drafted plan (not saved)   |
| GET/PUT/PATCH/DELETE | `plans/<id>/`              | Plan detail / edit / archive / delete            |
| GET              | `plans/<id>/calendar.ics`      | One-off calendar download                        |
| POST/DELETE      | `plan-steps/<id>/check-in/`    | Mark a step done / not done for `{date}`         |
| GET/POST/PATCH/DELETE | `account/calendar-feed/`  | Manage the private calendar subscription link   |
| GET              | `calendar/<token>.ics` _(public)_ | Live calendar feed (token is the credential)  |
| GET/POST         | `quick-check-in/` _(public)_   | Preview / confirm a check-in from a reminder email link |
| POST             | `reminders/unsubscribe/` _(public)_ | One-click unsubscribe (RFC 8058)              |
| GET/POST         | `notes/`                       | List / add session notes (`text` or `file` upload) → explanation |
| GET/PATCH/DELETE | `notes/<id>/`                  | Note detail / rename / delete                   |
| POST             | `notes/<id>/discuss/`          | Start a conversation with the notes in context  |
| GET              | `care-team/`                   | The client's therapists and what each can see   |
| GET/POST         | `care-team/invite/`, `care-team/accept/` | Review / accept a therapist's invitation |
| PATCH            | `care-team/<id>/`              | Change what this therapist can see              |
| GET/POST         | `screenings/mine/`             | Own results / self-report PHQ-9 or GAD-7        |

**Therapist API** (verified therapists, scoped to clients in their care; every call is audited):

| Method           | Path                                             | Description                                      |
| ---------------- | ------------------------------------------------ | ------------------------------------------------ |
| POST             | `therapists/register/` _(public)_                | Therapist sign-up with NPI                        |
| GET/POST         | `practice/clients/`                              | Roster / invite a client                          |
| GET              | `practice/clients/<id>/timeline/`                | Sessions and documents                            |
| POST             | `practice/clients/<id>/sessions/`, `documents/`  | Add a session / document                          |
| GET/PATCH        | `practice/clients/<id>/documents/<doc>/`         | Read / edit a draft                               |
| POST             | `.../documents/<doc>/sign/`, `.../addendum/`     | Sign (locks) / amend                              |
| POST             | `practice/clients/<id>/prep/`, `ask/`, `draft-note/` | Cited prep brief / ask the record / note draft |
| GET/POST         | `practice/clients/<id>/treatment-plans/`         | Treatment plans (AI draft, edit, sign)            |
| GET/POST         | `practice/clients/<id>/screenings/`, `homework/` | Screenings / assigned homework                    |
| GET              | `practice/clients/<id>/between-sessions/`        | Shared companion activity since the last session  |
| GET/POST         | `practice/risk-flags/`, `.../<id>/acknowledge/`  | Safety flag inbox                                 |

## 🛠️ Tech Stack

**Frontend:** React 19, TypeScript, Material UI 7 (+ MUI X Charts), TanStack Router & Query, Axios, react-markdown, Leaflet, Vite

**Backend:** Django 5.2, Django REST Framework, SimpleJWT, PostgreSQL + pgvector, Groq (gpt-oss-120b / gpt-oss-20b), FastEmbed local embeddings (bge-small-en-v1.5), cryptography (Fernet), WhiteNoise, gunicorn

**Infrastructure:** Railway (backend + PostgreSQL), Vercel (frontend), Docker

## ⚠️ Disclaimer

**This application is for informational and educational purposes only. It is NOT a substitute for professional mental health care.** If you are experiencing a mental health crisis, please contact:

- **988 Suicide & Crisis Lifeline**: Call or text 988
- **Crisis Text Line**: Text HOME to 741741
- **Emergency Services**: 911

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Rasheed Martin**

- GitHub: [@RasheedMartin](https://github.com/RasheedMartin)

## 🙏 Acknowledgments

- Embeddings by [FastEmbed](https://github.com/qdrant/fastembed) with BAAI bge-small-en-v1.5
- Powered by [Groq](https://groq.com/)

---

**Note**: Originally created during a 9-hour hackathon and evolved into a full-stack production application with AI capabilities.
