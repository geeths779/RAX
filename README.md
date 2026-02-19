# RAX — Resume Analysis eXpert

An AI-powered hiring platform that uses semantic understanding and explainable AI to screen, evaluate, and shortlist candidates — replacing keyword-based ATS filtering with a fair, transparent, and distributed multi-agent pipeline.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React.js + TypeScript (Vite) |
| Backend | Python FastAPI |
| Database | Supabase (PostgreSQL) |
| Vector Store | Qdrant |
| AI / LLM | Google Gemini (`gemini-1.5-pro` + `text-embedding-004`) |
| Agent SDK | `google-generativeai` (custom orchestrator) |
| Real-Time | WebSocket (FastAPI) |
| Deployment | Vercel (frontend), Railway/Render (backend), Qdrant Cloud |

---

## Architecture Overview

```
[Recruiter / Hiring Manager (Browser)]
          |
    [React Frontend]  <---WebSocket--->  [FastAPI Backend]
                                               |
                              ┌────────────────┼────────────────┐
                         [Supabase]        [Qdrant]       [Agent Pipeline]
                        (PostgreSQL)      (vectors)            |
                                              ┌────────────────┘
                                              ▼
                              ResumeParserAgent
                                    ↓
                              BiasFilterAgent
                                    ↓
                              EmbeddingAgent ──► Qdrant
                                    ↓
                              MatchingAgent ◄── Qdrant
                                    ↓
                              ScoringAgent (Gemini)
                                    ↓
                              FeedbackAgent (on demand)
```

---

## Repository Structure (Target)

```
repo-dev1/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml          # local dev: Qdrant only (Supabase is cloud-hosted)
├── docs/
│   └── initial_doc.md
├── frontend/                   # React + TypeScript (Person 3)
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/
│   │   └── store/
│   ├── vercel.json
│   └── vite.config.ts
└── backend/                    # Python FastAPI (Person 1 + Person 2)
    ├── app/
    │   ├── main.py
    │   ├── config.py
    │   ├── db/
    │   ├── models/
    │   ├── schemas/
    │   ├── api/
    │   │   └── routes/
    │   └── agents/             # AI pipeline (Person 2)
    ├── alembic/
    ├── tests/
    ├── Dockerfile
    └── requirements.txt
```

---

## Local Development Setup

### Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.11+
- A Google Gemini API key
- A [Supabase](https://supabase.com) account (free tier) — create a project to get `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY`
- A Qdrant Cloud account (free tier) or local Qdrant via Docker

### 1. Clone & configure env

```bash
git clone <repo-url>
cd repo-dev1
cp .env.example .env
# Fill in GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, DATABASE_URL (Supabase Postgres URI), QDRANT_URL, QDRANT_API_KEY, SECRET_KEY
```

### 2. Start local services

```bash
docker-compose up -d   # starts Qdrant locally (Supabase DB is cloud-hosted — no local Postgres needed)
```

### 3. Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Full Build Plan

### Phase 0 — Project Scaffolding (Shared)
- Update README, `.env.example`, `.gitignore`
- Create `docker-compose.yml` with `qdrant/qdrant` container only (named volume + health check)
- Create a Supabase project at [supabase.com](https://supabase.com); copy the connection string, project URL, and anon key into `.env`

---

## Engineer Assignments

---

### 👤 Person 1 — Backend Core (FastAPI + Supabase + Auth)

**Owns:** `backend/app/db/`, `backend/app/models/`, `backend/app/schemas/`, `backend/app/api/routes/`, `backend/alembic/`, `backend/app/api/dependencies.py`

#### Phase 1 — Backend Core

**Step 1 — Project bootstrap**
- Create `backend/` with `requirements.txt`:
  `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `psycopg2-binary`, `supabase`, `python-dotenv`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`
- `supabase` Python SDK (`supabase-py`) is included for Supabase client access (storage, realtime); core DB uses SQLAlchemy async over Supabase's Postgres connection string
- `backend/app/main.py` — FastAPI instance, CORS middleware, router inclusion, lifespan handler (DB init, Qdrant collection init)
- `backend/app/config.py` — Pydantic `Settings` class reading from env vars

**Step 2 — Database layer**
- `backend/app/db/session.py` — SQLAlchemy async engine pointing at Supabase Postgres URI (`DATABASE_URL`); `get_db` dependency
  - Supabase requires `?sslmode=require` appended to the connection string
- `backend/app/db/base.py` — declarative base
- `backend/app/db/supabase_client.py` — Supabase Python client init (`create_client(SUPABASE_URL, SUPABASE_ANON_KEY)`), used for file storage (resume files) and realtime if needed
- `backend/alembic/` — `alembic init`, configure to use async engine against Supabase

**Step 3 — SQLAlchemy Models** (`backend/app/models/`)
| Model | Key Fields |
|---|---|
| `user.py` | `id`, `email`, `hashed_password`, `role` (recruiter \| hiring_manager), `created_at` |
| `job.py` | `id`, `title`, `description`, `requirements_raw`, `embedding_id`, `created_by`, `status` |
| `candidate.py` | `id`, `name` (nullable), `email`, `created_at` |
| `resume.py` | `id`, `candidate_id`, `job_id`, `file_path`, `raw_text`, `parsed_json` (JSONB), `embedding_id`, `status` |
| `analysis.py` | `id`, `resume_id`, `overall_score`, `skills_score`, `experience_score`, `education_score`, `explanation`, `strengths` (JSONB), `gaps` (JSONB) |
| `feedback.py` | `id`, `candidate_id`, `job_id`, `content`, `sent_at` |

**Step 4 — Pydantic Schemas** (`backend/app/schemas/`)
- Request/response schemas for every model with field validation

**Step 5 — Auth**
- `backend/app/api/routes/auth.py` — `POST /auth/register`, `POST /auth/login` (returns JWT)
- `backend/app/api/dependencies.py` — `get_current_user` dependency (JWT decode)

**Step 6 — API Routes** (`backend/app/api/routes/`)
- `jobs.py` — CRUD for job postings; on create, fire JD embedding (call Person 2's `EmbeddingAgent`)
- `resumes.py` — bulk file upload; store to disk; trigger `PipelineOrchestrator` as `BackgroundTask`
- `candidates.py` — list candidates ranked by score for a job; filter/sort params
- `analysis.py` — fetch full analysis detail for a resume
- `feedback.py` — trigger `FeedbackAgent` (Person 2) and retrieve result

**Step 7 — Alembic migration**
- Generate initial revision from models
- Apply against Supabase cloud Postgres via `alembic upgrade head` (uses `DATABASE_URL` from `.env`)
- Alternatively: use Supabase dashboard SQL editor to review generated DDL before applying

**Step 8 — Unit tests** (`backend/tests/`)
- Test all route handlers with `httpx.AsyncClient` + mocked DB
- Test auth: register, login, protected route guard

---

### 👤 Person 2 — Agentic AI Pipeline (Gemini + Qdrant + WebSocket)

**Owns:** `backend/app/agents/`, `backend/app/api/routes/ws.py`

**Additional deps to add to `requirements.txt`:**
`google-generativeai`, `qdrant-client`, `pypdf2`, `python-docx`, `tiktoken`

#### Phase 2 — Multi-Agent Pipeline

All agents share a `PipelineContext` dataclass. Every agent is a Python class exposing `async def run(ctx: PipelineContext) -> PipelineContext`.

**Step 1 — Foundation**
- `backend/app/agents/pipeline_context.py`
  ```
  PipelineContext:
    resume_id, job_id, raw_text, parsed_resume, filtered_resume,
    resume_embedding, match_result, analysis, qdrant_point_id
  ```
- `backend/app/agents/base_agent.py` — abstract `BaseAgent`; initializes shared Gemini client (`genai.configure(api_key=...)`)

**Step 2 — ResumeParserAgent** (`resume_parser_agent.py`)
- Extract raw text from PDF (PyPDF2) and DOCX (python-docx)
- Gemini prompt → structured JSON extraction:
  `{ skills, experience [{title, company, duration, description}], education [{degree, institution, year}], name, email, phone }`
- Store result in `ctx.parsed_resume`

**Step 3 — BiasFilterAgent** (`bias_filter_agent.py`)
- Receive `ctx.parsed_resume`
- Gemini redaction prompt: anonymize `name`, gender signals, institution names (→ `[UNIVERSITY]`), nationality signals
- Store in `ctx.filtered_resume`; preserve original separately

**Step 4 — EmbeddingAgent** (`embedding_agent.py`)
- Use `models/text-embedding-004` (Gemini) to embed `ctx.filtered_resume` text
- Shared utility: also embed job description when a new job is created
- Upsert vectors into Qdrant (`resumes` collection + `job_descriptions` collection)
- Store `qdrant_point_id` in `ctx`

**Step 5 — MatchingAgent** (`matching_agent.py`)
- Query Qdrant: cosine similarity of resume embedding against target job embedding
- Return `semantic_similarity_score` (0.0–1.0) + top matching skill/experience snippets
- Store in `ctx.match_result`

**Step 6 — ScoringAgent** (`scoring_agent.py`)
- Gemini prompt combining: JD requirements + `ctx.filtered_resume` + `ctx.match_result`
- Output JSON:
  `{ overall_score, skills_score, experience_score, education_score, strengths[], gaps[], explanation }`
  (all scores 0–100)
- Persist result to `analyses` table via SQLAlchemy session

**Step 7 — FeedbackAgent** (`feedback_agent.py`)
- Invoked on demand via recruiter action (not in main pipeline run)
- Gemini prompt: generate 150–200 word constructive feedback email (professional tone, growth-focused)
- Persist to `feedback` table

**Step 8 — PipelineOrchestrator** (`orchestrator.py`)
- Accepts `resume_id` + `job_id`
- Runs agents in order: `ResumeParser → BiasFilter → Embedding → Matching → Scoring`
- Updates `resume.status`: `queued → processing → completed | failed`
- Publishes status events to WebSocket channel after each agent completes
- Designed as FastAPI `BackgroundTask` (fully async)

#### Phase 3 — Real-Time WebSocket

**Step 9 — WebSocket route** (`backend/app/api/routes/ws.py`)
- Endpoint: `WS /ws/pipeline/{job_id}`
- In-memory pub/sub manager; orchestrator publishes events as each agent finishes
- Event shape: `{ resume_id, candidate_name, stage, status, score? }`
- Stages: `parsing → filtering → embedding → matching → scoring → completed | failed`

**Step 10 — Unit tests** (`backend/tests/agents/`)
- Mock Gemini API and Qdrant client
- Test each agent's input/output contract in isolation
- Test orchestrator end-to-end with all agents mocked

---

### 👤 Person 3 — Frontend (React + TypeScript + Vite)

**Owns:** `frontend/`

**Key packages:** `react-router-dom`, `axios`, `zustand`, `react-hook-form`, `zod`, `tailwindcss`, `shadcn/ui`, `react-dropzone`, `recharts`

#### Phase 4 — Frontend

**Step 1 — Scaffold**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-router-dom axios zustand react-hook-form zod react-dropzone recharts
npx tailwindcss init
npx shadcn-ui@latest init
```

**Step 2 — Auth Store & Service** (`src/store/authStore.ts`, `src/services/authService.ts`)
- Zustand store: `{ token, user, login(), logout() }`
- Axios instance with JWT `Authorization` header interceptor
- Protected route wrapper checking token validity

**Step 3 — Auth Pages** (`src/pages/`)
- `LoginPage.tsx` — email/password form (react-hook-form + zod); `POST /auth/login`
- `RegisterPage.tsx` — email, password, role selector (recruiter | hiring_manager)

**Step 4 — App Shell** (`src/components/layout/`)
- `AppShell.tsx` — sidebar nav: Dashboard, Jobs, Candidates, Settings
- `ProtectedRoute.tsx` — redirects unauthenticated users to `/login`

**Step 5 — Dashboard** (`src/pages/DashboardPage.tsx`)
- Summary cards: active jobs, total resumes processed this week, avg time-to-screen
- Top candidates widget (ranked across all jobs)

**Step 6 — Job Management**
- `JobListPage.tsx` — table with status badges (Active, Closed, Draft); create button
- `CreateJobPage.tsx` / `JobDetailPage.tsx` — rich text area for job description + requirements; on save → `POST /jobs` (triggers JD embedding on backend)

**Step 7 — Resume Upload** (`src/pages/UploadPage.tsx`)
- `react-dropzone` multi-file drop zone (PDF/DOCX only)
- `POST /resumes/bulk` with `multipart/form-data`
- Opens WebSocket `WS /ws/pipeline/{job_id}` on upload start
- Real-time processing cards per resume: animated stage indicators (parsing → filtering → scoring) → score badge reveal on completion

**Step 8 — Candidate List** (`src/pages/CandidateListPage.tsx`)
- Ranked table: overall score, skills score, experience score, education score
- Sortable columns; filter by score range slider
- "Reveal Identity" toggle per row (shows/hides anonymized fields)
- Click row → Candidate Detail

**Step 9 — Candidate Detail** (`src/pages/CandidateDetailPage.tsx`)
- Radar chart (Recharts) — skills / experience / education scores
- Expandable "Strengths" and "Gaps" card lists from AI analysis
- Full AI explanation text block
- "Generate Feedback" button → `POST /feedback/{candidate_id}/{job_id}` → opens Feedback view

**Step 10 — Feedback View** (`src/pages/FeedbackPage.tsx`)
- Displays generated feedback text
- Copy-to-clipboard button
- "Mark as Sent" toggle (updates sent_at timestamp)

**Step 11 — API service layer** (`src/services/`)
- Typed Axios wrappers for all backend endpoints
- `useProcessingStream.ts` — custom React hook managing WebSocket lifecycle (connect, message handler, reconnect, cleanup)

**Step 12 — Deployment config**
- `frontend/vercel.json` — SPA rewrite rules (`"rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]`)
- Set `VITE_API_URL` env var in Vercel project settings

**Step 13 — Component tests**
- Vitest + React Testing Library
- Test: upload flow, score card rendering, auth guard redirect, WebSocket hook mock

---

## Phase 5 — Deployment (Shared / DevOps)

| Service | Platform | Notes |
|---|---|---|
| Frontend | **Vercel** | Auto-deploy from `frontend/` subfolder; set `VITE_API_URL` |
| Backend | **Railway** or **Render** | Dockerfile or Nixpacks; set all env vars |
| Database | **Supabase** (free tier) | Managed PostgreSQL; provides `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` |
| File Storage | **Supabase Storage** | Store uploaded resume PDFs/DOCX in a `resumes` bucket |
| Qdrant | **Qdrant Cloud** (free 1 GB cluster) | `QDRANT_URL` + `QDRANT_API_KEY` |

- `backend/Dockerfile` — multi-stage Python image; `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `backend/railway.toml` or `render.yaml` — backend deploy config
- `frontend/vercel.json` — SPA routing rewrites

---

## Phase 6 — Integration Verification (Shared)

1. `docker-compose up` → confirm Qdrant healthy (Postgres runs on Supabase cloud)
2. `alembic upgrade head` → confirm all tables created in Supabase (verify via Supabase dashboard → Table Editor)
3. Register two accounts (recruiter + hiring_manager)
4. Create a job posting → confirm JD vector stored in Qdrant
5. Upload 3 sample PDFs → watch WebSocket real-time stage cards
6. Confirm ranked candidate list with scores + explanations in frontend
7. Generate feedback for a candidate → verify content quality
8. Check Qdrant dashboard (`http://localhost:6333/dashboard`) → confirm resume vectors stored

---

## Environment Variables

See [.env.example](.env.example) for the full list. Required keys:

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Google Gemini API access |
| `DATABASE_URL` | Supabase PostgreSQL connection string (`postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:5432/postgres?sslmode=require`) |
| `SUPABASE_URL` | Supabase project URL (`https://[ref].supabase.co`) |
| `SUPABASE_ANON_KEY` | Supabase public anon key (for client SDK) |
| `QDRANT_URL` | Qdrant instance URL |
| `QDRANT_API_KEY` | Qdrant Cloud API key |
| `SECRET_KEY` | JWT signing secret |
| `CORS_ORIGINS` | Allowed frontend origins |
