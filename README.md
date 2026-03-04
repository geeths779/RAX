# RAX — Resume Analysis eXpert

An AI-powered hiring platform that uses semantic understanding and explainable AI to screen, evaluate, and shortlist candidates — replacing keyword-based ATS filtering with a fair, transparent, and distributed multi-agent pipeline powered by a hybrid knowledge graph + vector search architecture.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React.js + TypeScript (Vite) |
| Backend | Python FastAPI |
| Database | Supabase (PostgreSQL) |
| Knowledge Graph | Neo4j (structural reasoning, skill taxonomy, explainable matching) |
| Vector Store | Qdrant (semantic similarity, fuzzy matching) |
| AI / LLM | Google Gemini (`gemini-1.5-pro` + `text-embedding-004`) |
| Agent SDK | `google-generativeai` (custom orchestrator) |
| Real-Time | WebSocket (FastAPI) |
| Deployment | Vercel (frontend), Railway/Render (backend), Neo4j AuraDB, Qdrant Cloud |

---

## Architecture Overview

```
[Recruiter / Hiring Manager (Browser)]
          |
    [React Frontend]  <---WebSocket--->  [FastAPI Backend]
                                               |
                              ┌────────────────┼────────────────┐
                         [Supabase]    [Neo4j]    [Qdrant]    [Agent Pipeline]
                        (PostgreSQL) (Knowledge  (Vector           |
                                      Graph)     Store)           |
                                              ┌────────────────┘
                                              ▼
                              ResumeParserAgent
                                    ↓
                              BiasFilterAgent
                                    ↓
                        ┌─────────┴─────────┐  (parallel)
                        ▼                    ▼
              GraphIngestionAgent   EmbeddingAgent
                  → Neo4j              → Qdrant
                        └────────┬────────┘
                                ▼
                      HybridMatchingAgent
                      (Neo4j graph traversal +
                       Qdrant cosine similarity)
                                ↓
                        ScoringAgent (Gemini + hybrid context)
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
├── docker-compose.yml          # local dev: Neo4j + Qdrant (Supabase is cloud-hosted)
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
    │   │   ├── session.py          # SQLAlchemy async (Supabase Postgres)
    │   │   ├── base.py
    │   │   ├── supabase_client.py
    │   │   ├── neo4j_client.py     # Neo4j async driver + session factory
    │   │   └── qdrant_client.py    # Qdrant client init + collection setup
    │   ├── models/
    │   ├── schemas/
    │   ├── api/
    │   │   └── routes/
    │   └── agents/             # AI pipeline (Person 2)
    │       ├── pipeline_context.py
    │       ├── base_agent.py
    │       ├── resume_parser_agent.py
    │       ├── bias_filter_agent.py
    │       ├── graph_ingestion_agent.py   # Neo4j graph decomposition
    │       ├── embedding_agent.py         # Qdrant vector embedding
    │       ├── hybrid_matching_agent.py   # Fuses Neo4j + Qdrant signals
    │       ├── scoring_agent.py
    │       ├── feedback_agent.py
    │       └── orchestrator.py
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
- A Neo4j AuraDB account (free tier) or local Neo4j via Docker

### 1. Clone & configure env

```bash
git clone <repo-url>
cd repo-dev1
cp .env.example .env
# Fill in GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, DATABASE_URL (Supabase Postgres URI), NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, QDRANT_URL, QDRANT_API_KEY, SECRET_KEY
```

### 2. Start local services

```bash
docker-compose up -d   # starts Neo4j + Qdrant locally (Supabase DB is cloud-hosted — no local Postgres needed)
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
- Create `docker-compose.yml` with `neo4j:5-community` and `qdrant/qdrant` containers (named volumes + health checks)
- Create a Supabase project at [supabase.com](https://supabase.com); copy the connection string, project URL, and anon key into `.env`
- Create a Neo4j AuraDB free instance or use local Docker; copy `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` into `.env`

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
- `backend/app/main.py` — FastAPI instance, CORS middleware, router inclusion, lifespan handler (DB init, Neo4j driver init, Qdrant collection init)
- `backend/app/config.py` — Pydantic `Settings` class reading from env vars

**Step 2 — Database layer**
- `backend/app/db/session.py` — SQLAlchemy async engine pointing at Supabase Postgres URI (`DATABASE_URL`); `get_db` dependency
  - Supabase requires `?sslmode=require` appended to the connection string
- `backend/app/db/base.py` — declarative base
- `backend/app/db/supabase_client.py` — Supabase Python client init (`create_client(SUPABASE_URL, SUPABASE_ANON_KEY)`), used for file storage (resume files) and realtime if needed
- `backend/app/db/neo4j_client.py` — Neo4j async driver init (`AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))`); session factory for Cypher queries
- `backend/app/db/qdrant_client.py` — Qdrant client init (`QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)`); collection creation for `resumes` and `job_descriptions`
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
- `jobs.py` — CRUD for job postings; on create, fire JD embedding (call Person 2's `EmbeddingAgent`) and JD graph ingestion (call Person 2's `GraphIngestionAgent`)
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

### 👤 Person 2 — Agentic AI Pipeline (Gemini + Neo4j + Qdrant + WebSocket)

**Owns:** `backend/app/agents/`, `backend/app/api/routes/ws.py`

**Additional deps to add to `requirements.txt`:**
`google-generativeai`, `neo4j`, `qdrant-client`, `pypdf2`, `python-docx`

#### Phase 2 — Multi-Agent Pipeline

All agents share a `PipelineContext` dataclass. Every agent is a Python class exposing `async def run(ctx: PipelineContext) -> PipelineContext`.

**Step 1 — Foundation**
- `backend/app/agents/pipeline_context.py`
  ```
  PipelineContext:
    resume_id, job_id, raw_text, parsed_resume, filtered_resume,
    graph_node_id, qdrant_point_id, match_result, analysis
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

**Step 4 — GraphIngestionAgent** (`graph_ingestion_agent.py`)
- Decompose `ctx.filtered_resume` into graph nodes: `Candidate`, `Skill`, `Company`, `Role`, `Education`, `Institution`, `Certification`
- Create typed relationships: `HAS_SKILL`, `WORKED_AT`, `HELD_ROLE`, `STUDIED_AT`, `HAS_DEGREE`, `HAS_CERTIFICATION` with properties (years, proficiency, dates)
- Gemini normalizes skill names to canonical forms; classifies into `SkillCluster` nodes
- `MERGE` nodes and relationships into Neo4j (idempotent)
- Also used for JD ingestion: decomposes job requirements into `REQUIRES_SKILL`, `REQUIRES_DEGREE` relationships
- Store `graph_node_id` in `ctx`

**Step 5 — EmbeddingAgent** (`embedding_agent.py`)
- Runs **in parallel** with GraphIngestionAgent (no dependency between them)
- Use `models/text-embedding-004` (Gemini) to embed `ctx.filtered_resume` text
- Shared utility: also embed job description when a new job is created
- Upsert vectors into Qdrant (`resumes` collection + `job_descriptions` collection)
- Store `qdrant_point_id` in `ctx`

**Step 6 — HybridMatchingAgent** (`hybrid_matching_agent.py`)
- **Graph traversal (Neo4j):** Cypher queries for direct skill matches, similar skill matches (1-hop `IS_SIMILAR_TO`), skill gaps, experience depth, education fit, industry overlap
- **Vector similarity (Qdrant):** cosine similarity of resume embedding vs. job embedding; also retrieves top-5 nearest candidate neighbors
- **Score fusion:** weighted composite `hybrid_score = w1 × semantic_similarity + w2 × structural_match + w3 × experience_depth + w4 × education_fit` (weights configurable per job)
- **Graph enrichment feedback loop:** if Qdrant discovers high embedding similarity between skills without an `IS_SIMILAR_TO` edge in Neo4j, auto-create the edge
- Store in `ctx.match_result` (includes both graph paths and vector scores)

**Step 7 — ScoringAgent** (`scoring_agent.py`)
- Gemini prompt combining: JD requirements + `ctx.filtered_resume` + `ctx.match_result` (hybrid context with graph paths + semantic score)
**Step 7 cont.** — Output JSON:
  `{ overall_score, skills_score, experience_score, education_score, strengths[], gaps[], explanation }`
  (all scores 0–100; explanation references specific graph paths and skill matches)
- Persist result to `analyses` table via SQLAlchemy session

**Step 8 — FeedbackAgent** (`feedback_agent.py`)
- Invoked on demand via recruiter action (not in main pipeline run)
- Gemini prompt: generate 150–200 word constructive feedback email referencing specific skill matches, gaps, and adjacent skills from graph
- Persist to `feedback` table

**Step 9 — PipelineOrchestrator** (`orchestrator.py`)
- Accepts `resume_id` + `job_id`
- Runs agents in order: `ResumeParser → BiasFilter → [GraphIngestion || Embedding] (parallel) → HybridMatching → Scoring`
- Updates `resume.status`: `queued → processing → completed | failed`
- Publishes status events to WebSocket channel after each agent completes
- Designed as FastAPI `BackgroundTask` (fully async)

#### Phase 3 — Real-Time WebSocket

**Step 10 — WebSocket route** (`backend/app/api/routes/ws.py`)
- Endpoint: `WS /ws/pipeline/{job_id}`
- In-memory pub/sub manager; orchestrator publishes events as each agent finishes
- Event shape: `{ resume_id, candidate_name, stage, status, score? }`
- Stages: `parsing → filtering → graph_ingestion → embedding → hybrid_matching → scoring → completed | failed`

**Step 11 — Unit tests** (`backend/tests/agents/`)
- Mock Gemini API, Neo4j driver, and Qdrant client
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
- Real-time processing cards per resume: animated stage indicators (parsing → filtering → graph ingestion + embedding → hybrid matching → scoring) → score badge reveal on completion

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
| Knowledge Graph | **Neo4j AuraDB** (free tier) | 200K nodes, 400K relationships; `NEO4J_URI` + `NEO4J_USERNAME` + `NEO4J_PASSWORD` |
| Qdrant | **Qdrant Cloud** (free 1 GB cluster) | `QDRANT_URL` + `QDRANT_API_KEY` |

- `backend/Dockerfile` — multi-stage Python image; `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `backend/railway.toml` or `render.yaml` — backend deploy config
- `frontend/vercel.json` — SPA routing rewrites

---

## Phase 6 — Integration Verification (Shared)

1. `docker-compose up` → confirm Neo4j + Qdrant healthy (Postgres runs on Supabase cloud)
2. `alembic upgrade head` → confirm all tables created in Supabase (verify via Supabase dashboard → Table Editor)
3. Register two accounts (recruiter + hiring_manager)
4. Create a job posting → confirm JD vector stored in Qdrant + Job node with `REQUIRES_SKILL` edges in Neo4j
5. Upload 3 sample PDFs → watch WebSocket real-time stage cards
6. Confirm ranked candidate list with scores + explanations in frontend
7. Open Neo4j browser (`http://localhost:7474`) → run `MATCH (c:Candidate)-[:HAS_SKILL]->(s:Skill)<-[:REQUIRES_SKILL]-(j:Job) RETURN c, s, j` → verify graph connectivity
8. Check Qdrant dashboard (`http://localhost:6333/dashboard`) → confirm resume vectors stored
9. Generate feedback for a candidate → verify it references specific skill matches and gaps
10. Verify hybrid matching: compare graph structural score + vector similarity score in analysis detail

---

## Environment Variables

See [.env.example](.env.example) for the full list. Required keys:

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Google Gemini API access |
| `DATABASE_URL` | Supabase PostgreSQL connection string (`postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:5432/postgres?sslmode=require`) |
| `SUPABASE_URL` | Supabase project URL (`https://[ref].supabase.co`) |
| `SUPABASE_ANON_KEY` | Supabase public anon key (for client SDK) |
| `NEO4J_URI` | Neo4j connection URI (`bolt://localhost:7687` or AuraDB URI) |
| `NEO4J_USERNAME` | Neo4j username (default: `neo4j`) |
| `NEO4J_PASSWORD` | Neo4j password |
| `QDRANT_URL` | Qdrant instance URL |
| `QDRANT_API_KEY` | Qdrant Cloud API key |
| `SECRET_KEY` | JWT signing secret |
| `CORS_ORIGINS` | Allowed frontend origins |
