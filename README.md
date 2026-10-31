# TherapyBot 🧠💬

A full-stack AI-powered mental health support application that provides evidence-based therapeutic guidance through natural language conversations. Built with React, Django, and LlamaIndex for intelligent document retrieval.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/Django-5.2+-green.svg)
![React](https://img.shields.io/badge/React-18+-61DAFB.svg)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.14+-purple.svg)

## 🌟 Features

- **AI-Powered Therapy Conversations**: Leverages Groq (gpt-oss-120b) and LlamaIndex for context-aware, evidence-based responses
- **Multiple Therapy Modalities**: Supports various therapy types including CBT, DBT, Family Therapy, and Teen Counseling
- **Crisis Detection**: Automatically detects crisis messages and directs users to appropriate resources
- **Knowledge Base Integration**: Built on curated mental health resources from trusted sources
- **Persistent Conversations**: Multi-turn chats with history, saved per user
- **Modern React Frontend**: Responsive Material UI chat interface with light and dark mode
- **Django REST API**: Robust backend with RESTful endpoints and JWT authentication
- **Vector Search**: Semantic search over a curated, clinician-reviewable knowledge base using local embeddings

## 🏗️ Architecture

```
TherapyBot/
├── backend/
│   ├── djangoProject/          # Django settings, URLs, WSGI
│   ├── therapybot/
│   │   ├── ai.py               # LlamaIndex retrieval + Groq chat, crisis detection
│   │   ├── models.py           # Conversation / Message
│   │   ├── views.py            # REST API
│   │   ├── tests.py            # API + safety tests (AI mocked)
│   │   └── management/commands/build_index.py
│   ├── knowledge/              # Markdown reference articles (source for retrieval)
│   ├── storage/                # Persisted vector index (shipped in the Docker image)
│   ├── Dockerfile
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── pages/              # Home, Chat, NotFound
    │   ├── components/         # Auth pages, Navbar, chat/ (sidebar, bubbles, composer)
    │   ├── context/            # AuthContext (tokens + current user)
    │   ├── api/                # Axios client with token refresh, shared types
    │   └── theme.ts            # MUI theme (light + dark)
    ├── vercel.json
    └── .env.example
```

## 🚀 Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL 17 with the pgvector extension (vector search runs in the database)
- Node.js 20+
- [Groq API key](https://console.groq.com) (free)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
brew install postgresql@17 pgvector && brew services start postgresql@17 && createdb therapybot
cp .env.example .env            # then fill in GROQ_API_KEY and SECRET_KEY
python manage.py migrate
python manage.py runserver      # http://localhost:8000
```

Run the tests with `python manage.py test`. To measure reply quality and safety against real models after
changing prompts or models, run `python manage.py run_evals` (see `backend/evals/README.md`).

The bot's reference material is MedlinePlus articles (imported with `python manage.py import_articles`,
editable in the admin) plus the skill guides in `backend/knowledge/` (each needs clinical review before production). After editing them, rebuild the committed
vector index with `python manage.py build_index`. Embeddings run locally (fastembed, `bge-small-en-v1.5`),
so no embedding API key is needed; the model (~70 MB) downloads on first use.

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
| `DATABASE_URL`                                                               | ✅       | Injected by the Railway Postgres plugin                               |
| `ALLOWED_HOSTS`                                                              |          | Extra hostnames; the Railway domain is added automatically            |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` |          | SMTP for password-reset emails (printed to logs if unset)             |
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

## 🛠️ Tech Stack

**Frontend:** React 19, TypeScript, Material UI 7, TanStack Router & Query, Axios, react-markdown, Vite

**Backend:** Django 5.2, Django REST Framework, SimpleJWT, LlamaIndex, Groq (gpt-oss-120b), fastembed local embeddings (bge-small-en-v1.5), WhiteNoise, gunicorn

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
- Built with [LlamaIndex](https://www.llamaindex.ai/)
- Powered by [Groq](https://groq.com/)

---

**Note**: Originally created during a 9-hour hackathon and evolved into a full-stack production application with AI capabilities.
