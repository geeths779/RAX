# RAX — Backend Architecture

## Technology Stack

| Layer          | Technology                          |
|----------------|-------------------------------------|
| Framework      | FastAPI (async, Python 3.14)        |
| ORM            | SQLAlchemy 2.0 (async, asyncpg)     |
| Primary DB     | PostgreSQL via Supabase             |
| Graph DB       | Neo4j 5 (async driver)              |
| Vector DB      | Qdrant (gRPC client)                |
| LLM            | Google Gemini (google-generativeai) |
| Auth           | JWT (python-jose) + bcrypt          |
| Migrations     | Alembic                             |
| File Storage   | Supabase Storage                    |
| Real-time      | WebSocket (FastAPI native)          |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              ← FastAPI app, lifespan, CORS, router registration
│   ├── config.py            ← Pydantic Settings (env vars)
│   │
│   ├── api/
│   │   ├── dependencies.py  ← JWT auth: get_current_user, require_role
│   │   └── routes/
│   │       ├── auth.py      ← POST /register, /login
│   │       ├── jobs.py      ← CRUD /jobs
│   │       ├── resumes.py   ← POST /upload, GET /status
│   │       ├── candidates.py← GET /jobs/:id/candidates
│   │       ├── analysis.py  ← GET /resumes/:id/analysis
│   │       ├── feedback.py  ← POST + GET /feedback
│   │       └── ws.py        ← WebSocket /ws/pipeline/:jobId
│   │
│   ├── models/              ← SQLAlchemy ORM models
│   │   ├── user.py          ← User (id, email, hashed_password, role)
│   │   ├── job.py           ← Job (id, title, description, requirements_raw, status)
│   │   ├── candidate.py     ← Candidate (id, name, email, phone)
│   │   ├── resume.py        ← Resume (id, candidate_id, job_id, pipeline_status, ...)
│   │   ├── analysis.py      ← Analysis (scores, explanation, strengths, gaps)
│   │   ├── feedback.py      ← Feedback (content text)
│   │   └── enums.py         ← UserRole, PipelineStatus, JobStatus
│   │
│   ├── schemas/             ← Pydantic request/response schemas
│   │   ├── user.py, job.py, resume.py, candidate.py, analysis.py, feedback.py
│   │
│   ├── db/                  ← Database clients & session management
│   │   ├── session.py       ← async engine + get_db dependency
│   │   ├── base.py          ← DeclarativeBase
│   │   ├── neo4j_client.py  ← Neo4j async driver singleton
│   │   ├── qdrant_client.py ← Qdrant client singleton
│   │   └── supabase_client.py ← Supabase client singleton
│   │
│   └── agents/              ← AI Pipeline agents
│       ├── orchestrator.py
│       ├── pipeline_context.py
│       ├── base_agent.py
│       ├── gemini_client.py
│       ├── resume_parser_agent.py
│       ├── bias_filter_agent.py
│       ├── graph_ingestion_agent.py
│       ├── embedding_agent.py
│       ├── hybrid_matching_agent.py
│       ├── scoring_agent.py
│       └── feedback_agent.py
│
├── alembic/                 ← DB migrations
├── tests/                   ← pytest async test suite
├── requirements.txt
└── .env / .env.example
```

---

## Application Lifecycle

```
Startup (lifespan):
  1. init_neo4j_driver()      → connects to bolt://localhost:7687
  2. init_qdrant_client()     → connects to http://localhost:6333
  3. init_supabase_client()   → connects to Supabase cloud
  (each is best-effort — app starts even if a service is unavailable)

Shutdown (lifespan):
  1. close_neo4j_driver()     → graceful close
  2. close_db_engine()        → dispose SQLAlchemy async engine
```

---

## Authentication System

```
┌──────────┐   POST /api/auth/register    ┌──────────────────┐
│  Client  │ ─────────────────────────►   │  auth.py          │
│          │   { email, password,          │  1. Check dupe    │
│          │     full_name, role }         │  2. bcrypt hash   │
│          │                               │  3. Insert User   │
│          │◄──────────────────────────    │  4. Return user   │
│          │   UserResponse (201)          └──────────────────┘
│          │
│          │   POST /api/auth/login        ┌──────────────────┐
│          │ ─────────────────────────►   │  auth.py          │
│          │   { email, password }         │  1. Find user     │
│          │                               │  2. bcrypt verify │
│          │◄──────────────────────────    │  3. Sign JWT      │
│          │   { access_token }            │     sub=user_id   │
│          │                               │     role=role     │
│          │                               │     exp=60min     │
│          │                               └──────────────────┘
│          │
│  Every   │   Authorization: Bearer <jwt>
│ request  │ ─────────────────────────►   dependencies.py
│          │                               get_current_user():
│          │                                 1. Decode JWT
│          │                                 2. Load User from DB
│          │                                 3. Return User object
│          │
│          │                               require_role("recruiter"):
│          │                                 1. get_current_user
│          │                                 2. Check user.role in allowed
│          │                                 3. 403 if not authorized
└──────────┘
```

---

## AI Pipeline Architecture

When a resume is uploaded (`POST /api/resumes/upload`), the pipeline runs **asynchronously as a background task**:

```
┌─────────────────────────────────────────────────────────────┐
│                   PipelineOrchestrator                       │
│                                                             │
│  PipelineContext (shared state passed through all agents)   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ resume_id, job_id, file_bytes, filename              │   │
│  │ raw_text, parsed_resume, filtered_resume             │   │
│  │ neo4j_node_id, qdrant_point_id                       │   │
│  │ match_result, analysis, error                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Stage 1: ResumeParserAgent                                 │
│    Input:  file_bytes (PDF/DOCX)                            │
│    Action: Extract text → send to Gemini for structured     │
│            parsing → produces JSON with name, skills,       │
│            experience, education sections                   │
│    Output: ctx.raw_text, ctx.parsed_resume                  │
│                                                             │
│  Stage 2: BiasFilterAgent                                   │
│    Input:  ctx.parsed_resume                                │
│    Action: Removes PII (name, email, phone, gender, age)    │
│            via Gemini or rule-based redaction                │
│    Output: ctx.filtered_resume (anonymized)                 │
│                                                             │
│  Stage 3: GraphIngestionAgent                               │
│    Input:  ctx.filtered_resume, resume_id                   │
│    Action: Creates Neo4j nodes (Resume, Skill, Company,     │
│            Degree) and relationships (HAS_SKILL, WORKED_AT, │
│            HAS_DEGREE) in the knowledge graph               │
│    Output: ctx.neo4j_node_id                                │
│                                                             │
│  Stage 4: EmbeddingAgent                                    │
│    Input:  ctx.filtered_resume text                         │
│    Action: Generates vector embedding via Gemini → stores   │
│            in Qdrant with resume metadata                   │
│    Output: ctx.qdrant_point_id                              │
│                                                             │
│  Stage 5: HybridMatchingAgent                               │
│    Input:  resume_id, job_id, Neo4j driver, Qdrant client   │
│    Action: Computes fusion score from:                      │
│            - Neo4j: direct skill match, similar skill match │
│            - Qdrant: cosine similarity of embeddings        │
│            - Neo4j: education degree comparison             │
│            Weights: 50% structural + 30% semantic +         │
│                     15% experience + 5% education           │
│    Output: ctx.match_result = {                             │
│              matched_skills, similar_skills, skill_gaps,    │
│              structural_score, semantic_score,              │
│              education_score, experience_score,             │
│              overall_score, graph_paths                     │
│            }                                                │
│                                                             │
│  Stage 6: ScoringAgent                                      │
│    Input:  ctx.match_result, ctx.parsed_resume              │
│    Action: Sends all data to Gemini for multi-dimensional   │
│            scoring and natural language explanation          │
│    Output: ctx.analysis = {                                 │
│              overall_score, skills_score,                    │
│              experience_score, education_score,              │
│              explanation, strengths[], gaps[]                │
│            }                                                │
│                                                             │
│  After all stages → persist results to PostgreSQL:          │
│    - Update Resume row (pipeline_status, raw_text, etc.)    │
│    - Create Analysis row (all scores + explanation)         │
└─────────────────────────────────────────────────────────────┘
```

### Status Broadcasting

Each stage transition emits a WebSocket message via the `ConnectionManager`:

```
Orchestrator → ws_callback(resume_id, stage, "in_progress")
Agent runs...
Orchestrator → ws_callback(resume_id, stage, "complete")
  → next stage
```

All connected WebSocket clients on `/ws/pipeline/:jobId` receive these updates in real time.

---

## Database Schema (ERD)

```
┌──────────┐       ┌──────────┐       ┌───────────┐
│  User    │       │   Job    │       │ Candidate │
├──────────┤       ├──────────┤       ├───────────┤
│ id (PK)  │──┐    │ id (PK)  │──┐    │ id (PK)   │
│ email    │  │    │ title    │  │    │ name      │
│ hashed_pw│  │    │ desc     │  │    │ email     │
│ full_name│  │    │ req_raw  │  │    │ phone     │
│ role     │  │    │ status   │  │    │ created_at│
│ created_at│ │    │created_by│◄─┘    └─────┬─────┘
└──────────┘  │    │embed_id  │             │
              │    │created_at│             │
              │    └──────┬───┘             │
              │           │                 │
              │    ┌──────▼──────┐          │
              │    │   Resume    │          │
              │    ├─────────────┤          │
              │    │ id (PK)     │          │
              │    │candidate_id │◄─────────┘
              │    │ job_id      │
              │    │ file_path   │
              │    │pipeline_stat│
              │    │ raw_text    │
              │    │ parsed_json │
              │    │anonym_json  │
              │    │ embed_id    │
              │    │ created_at  │
              │    └──────┬──────┘
              │           │
              │    ┌──────▼──────┐    ┌──────────────┐
              │    │  Analysis   │    │  Feedback     │
              │    ├─────────────┤    ├──────────────┤
              │    │ id (PK)     │    │ id (PK)      │
              │    │ resume_id   │    │candidate_id  │
              │    │ job_id      │    │ job_id       │
              │    │overall_scor │    │ resume_id    │
              │    │skills_score │    │ content      │
              │    │exp_score    │    │ sent_at      │
              │    │edu_score    │    │ created_at   │
              │    │semantic_sim │    └──────────────┘
              │    │structural_m │
              │    │explanation  │
              │    │strengths[]  │
              │    │gaps[]       │
              │    │graph_paths[]│
              │    │ created_at  │
              │    └─────────────┘
```

### Enums

| Enum           | Values                                           |
|----------------|--------------------------------------------------|
| UserRole       | `recruiter`, `hiring_manager`                    |
| PipelineStatus | `uploaded`, `processing`, `completed`, `failed`  |
| JobStatus      | `draft`, `active`, `closed`                      |

---

## External Service Integrations

### Neo4j (Knowledge Graph)

- **Purpose**: Stores skills, companies, degrees, and their relationships to resumes and jobs.
- **Used by**: `GraphIngestionAgent` (write), `HybridMatchingAgent` (read queries).
- **Key queries**:
  - `DIRECT_SKILL_MATCH`: Finds skills shared between resume and job.
  - `SIMILAR_SKILL_MATCH`: Finds related skills via 2-hop graph traversal.
  - `EDUCATION_COMPARISON`: Compares resume degree level against job requirements.

### Qdrant (Vector Search)

- **Purpose**: Stores embedding vectors of resumes and jobs for semantic similarity search.
- **Used by**: `EmbeddingAgent` (write), `HybridMatchingAgent` (similarity search).
- **Collection**: Uses deterministic UUIDs derived from `resume_id` / `job_id` for point IDs.
- **Similarity**: Cosine distance between resume embedding and job embedding.

### Google Gemini (LLM)

- **Purpose**: Powers all AI reasoning — parsing, filtering, scoring, feedback.
- **Used by**: All agents via `GeminiClient` wrapper.
- **Model**: Configurable via `GOOGLE_API_KEY` env var.

### Supabase

- **PostgreSQL**: Primary relational database (users, jobs, resumes, analyses, feedback).
- **Storage**: File storage for uploaded resume PDFs/DOCXs.
- **Connection**: `DATABASE_URL` for SQLAlchemy, `SUPABASE_URL` + `SUPABASE_ANON_KEY` for storage.

---

## Configuration (Environment Variables)

| Variable                      | Required | Default                |
|-------------------------------|----------|------------------------|
| `GOOGLE_API_KEY`              | Yes      | —                      |
| `DATABASE_URL`                | Yes      | —                      |
| `SUPABASE_URL`                | Yes      | —                      |
| `SUPABASE_ANON_KEY`           | Yes      | —                      |
| `NEO4J_URI`                   | No       | `bolt://localhost:7687`|
| `NEO4J_USERNAME`              | No       | `neo4j`                |
| `NEO4J_PASSWORD`              | No       | `rax_dev_password`     |
| `QDRANT_URL`                  | No       | `http://localhost:6333`|
| `QDRANT_API_KEY`              | No       | (empty)                |
| `SECRET_KEY`                  | No       | `changeme`             |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No       | `60`                   |
| `CORS_ORIGINS`                | No       | `http://localhost:5173`|

---

## Error Handling Strategy

- **Agent failures are non-blocking**: If Neo4j, Qdrant, or Gemini are down, the route handlers catch exceptions and log warnings. The app continues running.
- **Pipeline failures**: If any agent fails during resume processing, `ctx.error` is set, `pipeline_status` is marked `failed`, and the WebSocket broadcasts the failure.
- **HTTP errors**: Standard FastAPI `HTTPException` with appropriate status codes (400, 401, 403, 404).
- **Background tasks**: Pipeline runs in `BackgroundTasks` so the upload API returns immediately without blocking.
