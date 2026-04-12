# RAX — Resume Analysis eXpert

## A Multi-Agent AI System for Bias-Aware Resume Screening Using Knowledge Graphs, Vector Embeddings, and Explainable Scoring

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Technology Stack](#4-technology-stack)
5. [Backend Architecture](#5-backend-architecture)
6. [AI Agent Pipeline — The Core Engine](#6-ai-agent-pipeline--the-core-engine)
7. [Database Architecture — Three-Database Strategy](#7-database-architecture--three-database-strategy)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Real-Time Communication — Server-Sent Events](#9-real-time-communication--server-sent-events)
10. [Authentication and Authorization](#10-authentication-and-authorization)
11. [Email Notification System](#11-email-notification-system)
12. [Deployment Architecture](#12-deployment-architecture)
13. [Concurrency and Performance Optimizations](#13-concurrency-and-performance-optimizations)
14. [Bias Prevention Strategy](#14-bias-prevention-strategy)
15. [Explainability and Transparency](#15-explainability-and-transparency)
16. [Complete Data Flow — End to End](#16-complete-data-flow--end-to-end)
17. [API Endpoint Reference](#17-api-endpoint-reference)
18. [Local Development Setup](#18-local-development-setup)

---

## 1. Executive Summary

RAX (Resume Analysis eXpert) is a full-stack AI-powered resume screening platform that replaces traditional keyword-matching Applicant Tracking Systems (ATS) with a multi-agent pipeline combining:

- **Knowledge Graphs** (Neo4j) for structural skill-to-job matching and skill taxonomy discovery
- **Vector Embeddings** (Qdrant + Google Gemini) for semantic understanding of resumes beyond exact keyword hits
- **Large Language Models** (Google Gemini 2.5 Flash) for intelligent parsing, experience verification, and explainable scoring
- **Deterministic Bias Filtering** to anonymize protected attributes before any scoring occurs

The system processes each resume through a 6-stage pipeline, producing a multi-dimensional score (Skills, Experience, Education) with human-readable explanations, traceable graph paths, and actionable strengths/gaps analysis. Recruiters interact through a modern React dashboard with real-time pipeline progress updates via Server-Sent Events (SSE).

---

## 2. Problem Statement

Traditional ATS platforms suffer from three critical shortcomings:

1. **Keyword-Only Matching**: They rely on exact string matching — a candidate with "React.js" gets rejected if the job says "ReactJS". This approach cannot understand that "PostgreSQL" and "SQL databases" are semantically related.

2. **Opaque Scoring**: Most ATS systems produce a single score with no explanation. Recruiters cannot understand *why* a candidate scored high or low, making it impossible to audit or trust the result.

3. **Inherent Bias**: Systems that score based on university names, company prestige, or name-inferred demographics introduce bias into the hiring process. Traditional ATS provides no mechanism to prevent this.

**RAX addresses all three** by combining graph-based structural matching (for skill relationships), vector-based semantic similarity (for meaning-level understanding), LLM-based scoring (for nuanced evaluation with explanations), and deterministic anonymization (for bias prevention).

---

## 3. System Architecture Overview

RAX follows a **four-tier architecture**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React 19)                          │
│   Landing Page │ Dashboard │ Job Management │ Candidate Review       │
│                     Deployed on: Vercel                              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ HTTPS / SSE
┌───────────────────────────▼─────────────────────────────────────────┐
│                     BACKEND (FastAPI + Python)                       │
│     REST API │ SSE Broadcasting │ Multi-Agent AI Pipeline            │
│                     Deployed on: Render                              │
└──────┬──────────────┬──────────────┬──────────────┬─────────────────┘
       │              │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐
│  Supabase   │ │   Neo4j    │ │  Qdrant  │ │  Supabase  │
│ PostgreSQL  │ │  AuraDB    │ │  Cloud   │ │  Storage   │
│             │ │            │ │          │ │            │
│ Users, Jobs │ │ Knowledge  │ │  Vector  │ │  Resume    │
│ Resumes,    │ │ Graph:     │ │Embeddings│ │  File      │
│ Analyses,   │ │ Skills,    │ │  (768d)  │ │  Storage   │
│ Feedback    │ │ Companies, │ │          │ │  (PDF,     │
│             │ │ Education  │ │          │ │   DOCX)    │
└─────────────┘ └────────────┘ └──────────┘ └────────────┘
```

**Data flows unidirectionally** from the frontend through the backend to the databases. The only server-to-client push is the SSE pipeline status stream.

---

## 4. Technology Stack

### 4.1 Backend

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.14 | Core language — chosen for its AI/ML ecosystem |
| **FastAPI** | 0.115.x | Async web framework — native async/await, automatic OpenAPI docs |
| **Uvicorn** | 0.34.x | ASGI server — high-performance async HTTP serving |
| **SQLAlchemy** | 2.0.x (async) | ORM — async database operations with type-safe models |
| **asyncpg** | 0.31.x | PostgreSQL async driver — zero-copy binary protocol |
| **Alembic** | 1.15.x | Database migrations — version-controlled schema changes |
| **Google Gemini** (google-genai) | ≥1.72 | LLM for parsing, experience extraction, and scoring |
| **Neo4j Python Driver** | 5.28.x | Knowledge graph client — async Cypher query execution |
| **Qdrant Client** | 1.17.x | Vector database client — embedding storage and similarity search |
| **Supabase SDK** | 2.15.x | Cloud storage client — resume file uploads |
| **python-jose** | 3.4.x | JWT token creation/validation for authentication |
| **passlib + bcrypt** | 1.7.x | Password hashing — industry-standard bcrypt |
| **PyPDF2** | 3.0.x | PDF text extraction |
| **python-docx** | 1.1.x | DOCX text extraction |
| **httpx** | 0.28.x | Async HTTP client — used for Resend email API |
| **Pydantic Settings** | 2.9.x | Configuration management with environment variable binding |

### 4.2 Frontend

| Technology | Version | Purpose |
|---|---|---|
| **React** | 19.2.x | UI framework — component-based reactive rendering |
| **TypeScript** | ~5.9 | Type safety — compile-time error detection |
| **Vite** | 8.0.x | Build tool — fast HMR, optimized production bundles |
| **Tailwind CSS** | 4.2.x | Utility-first styling — rapid UI development |
| **React Router** | 7.13.x | Client-side routing with protected route guards |
| **Zustand** | 5.0.x | State management — lightweight global store for auth |
| **Axios** | 1.13.x | HTTP client with interceptors for JWT auth |
| **Recharts** | 3.8.x | Data visualization — radar charts for score display |
| **Framer Motion** | 12.38.x | Animations — page transitions, progress indicators |
| **Lucide React** | 0.577.x | Icon library — consistent UI iconography |
| **React Hook Form + Zod** | 7.72 / 4.3 | Form management with schema-based validation |
| **React Dropzone** | 15.0.x | Drag-and-drop file upload interface |

### 4.3 Databases

| Database | Hosting | Purpose |
|---|---|---|
| **PostgreSQL** | Supabase (cloud) | Primary relational store — users, jobs, resumes, analyses, feedback |
| **Neo4j** | AuraDB Free Tier | Knowledge graph — skills, relationships, career topology |
| **Qdrant** | Qdrant Cloud Free | Vector store — 768-dimensional embeddings for semantic search |

### 4.4 AI Models

| Model | Provider | Purpose |
|---|---|---|
| **Gemini 2.5 Flash** | Google | Resume parsing, experience extraction, scoring (text generation) |
| **text-embedding-004** | Google | 768-dimensional embeddings for resumes and job descriptions |

### 4.5 Infrastructure

| Service | Provider | Purpose |
|---|---|---|
| **Backend Hosting** | Render | Python FastAPI deployment with auto-deploy from Git |
| **Frontend Hosting** | Vercel | Static React SPA deployment with CDN |
| **File Storage** | Supabase Storage | Resume file storage (PDF, DOCX) |
| **Email Delivery** | Resend (primary) + Gmail SMTP (fallback) | Candidate notification emails |
| **DNS/SSL** | Automatic via Render + Vercel | HTTPS certificates managed by platform |

---

## 5. Backend Architecture

### 5.1 Project Structure

The backend follows a **layered architecture** with clear separation of concerns:

```
backend/
├── app/
│   ├── main.py              ← FastAPI application entry point, middleware, route registration
│   ├── config.py            ← Pydantic Settings: all environment variable bindings
│   ├── agents/              ← AI Pipeline (6 agents + orchestrator + shared context)
│   │   ├── orchestrator.py     ← Pipeline controller — runs agents in optimized order
│   │   ├── pipeline_context.py ← Shared data object passed between all agents
│   │   ├── base_agent.py       ← Abstract base with LLM/embedding helpers + rate limiting
│   │   ├── resume_parser_agent.py
│   │   ├── bias_filter_agent.py
│   │   ├── experience_extractor.py
│   │   ├── graph_ingestion_agent.py
│   │   ├── embedding_agent.py
│   │   ├── hybrid_matching_agent.py
│   │   ├── scoring_agent.py
│   │   └── feedback_agent.py
│   ├── api/
│   │   ├── dependencies.py    ← Shared dependency injection (get_current_user, get_db)
│   │   └── routes/            ← All REST endpoints + SSE
│   │       ├── auth.py        ← Register, login, me
│   │       ├── jobs.py        ← CRUD for job postings
│   │       ├── resumes.py     ← Upload (single + batch), pipeline trigger
│   │       ├── candidates.py  ← List with scores, sort, filter
│   │       ├── analysis.py    ← Detailed scoring breakdown
│   │       ├── feedback.py    ← AI-generated candidate feedback
│   │       ├── notifications.py ← Email sending
│   │       └── sse.py         ← Server-Sent Events for real-time updates
│   ├── db/
│   │   ├── session.py         ← SQLAlchemy async engine + session factory
│   │   ├── neo4j_client.py    ← Neo4j driver initialization + connection management
│   │   ├── qdrant_client.py   ← Qdrant client initialization
│   │   └── supabase_client.py ← Supabase storage client
│   ├── models/               ← SQLAlchemy ORM models (database tables)
│   ├── schemas/              ← Pydantic schemas (API request/response validation)
│   └── services/
│       └── email_service.py  ← Dual-provider email delivery (Resend + SMTP)
├── alembic/                  ← Database migration scripts
├── tests/                    ← Pytest test suite
└── requirements.txt
```

### 5.2 Application Startup

When the server starts, `main.py` executes a **lifespan** routine that verifies connectivity to all four external services:

1. **Neo4j** — Calls `driver.verify_connectivity()` to confirm graph database is reachable
2. **Qdrant** — Calls `get_collections()` to verify the vector store responds
3. **Supabase Storage** — Initializes the storage client for file uploads
4. **PostgreSQL** — Executes `SELECT 1` through SQLAlchemy to test the connection pool

If any service fails, the application **aborts startup** with a detailed error listing which services are unavailable. This fail-fast approach prevents the server from accepting requests it cannot fulfill.

### 5.3 Middleware Stack

- **CORS Middleware**: Configured with `allow_origins` from the `CORS_ORIGINS` environment variable (comma-separated). Allows credentials, all methods, and all headers for the SPA frontend.
- **Request Logging Middleware**: Logs every HTTP request with method, path, response status code, and elapsed time in milliseconds. Requests returning 400+ are logged at WARNING level.
- **Validation Error Handler**: Overrides FastAPI's default 422 handler to log detailed validation errors for debugging.

---

## 6. AI Agent Pipeline — The Core Engine

The pipeline is the heart of RAX. Each uploaded resume passes through **6 specialized AI agents** orchestrated by a central controller. The agents communicate through a shared `PipelineContext` dataclass that accumulates results as it flows through each stage.

### 6.1 Pipeline Flow Diagram

```
Resume Upload (PDF/DOCX)
        │
        ▼
┌─────────────────────┐
│  Stage 1: PARSING   │  ← Gemini LLM extracts structured fields
│  ResumeParserAgent   │     (name, skills, experience, education)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  Stage 2: FILTERING │  ← Deterministic regex — NO LLM call
│  BiasFilterAgent     │     Anonymizes PII, pronouns, institutions
└─────────┬───────────┘
          │
          ├────────────────────┬──────────────────────┐
          ▼                    ▼                      ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ EXPERIENCE       │ │ GRAPH INGESTION  │ │ EMBEDDING        │
│ EXTRACTION       │ │                  │ │                  │
│                  │ │ Writes Candidate,│ │ Generates 768-d  │
│ Gemini verifies  │ │ Skill, Company,  │ │ vector, stores   │
│ dates, calculates│ │ Education nodes  │ │ in Qdrant with   │
│ total years,     │ │ + relationships  │ │ rich metadata    │
│ seniority level  │ │ into Neo4j       │ │ payload          │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │    PARALLEL (asyncio.gather)                │
         └───────────────┬─────────────────────────────┘
                         ▼
┌──────────────────────────────────┐
│  Stage 4: HYBRID MATCHING        │
│                                  │
│  Neo4j graph traversal (50%)     │
│  + Qdrant cosine similarity (30%)│
│  + Experience years match (15%)  │
│  + Education level match (5%)    │
│                                  │
│  → Produces hybrid_score 0–1     │
└────────────────┬─────────────────┘
                 ▼
┌──────────────────────────────────┐
│  Stage 5: SCORING                │
│                                  │
│  Gemini evaluates resume vs job  │
│  using all accumulated data.     │
│  Produces:                       │
│    • overall_score (0–100)       │
│    • skills_score (0–100)        │
│    • experience_score (0–100)    │
│    • education_score (0–100)     │
│    • strengths[]                 │
│    • gaps[]                      │
│    • human-readable explanation  │
└──────────────────────────────────┘
```

### 6.2 Stage 1 — Resume Parsing (ResumeParserAgent)

**Purpose**: Convert raw PDF/DOCX files into structured data.

**Process**:
1. The agent first extracts raw text from the file using **PyPDF2** (for PDF) or **python-docx** (for DOCX)
2. The raw text is then sent to **Google Gemini 2.5 Flash** with a structured prompt requesting specific JSON output
3. The LLM extracts: `name`, `email`, `phone`, `skills` (with years and proficiency), `experience` (with title, company, duration), and `education` (with degree, field, institution, year)
4. The response is validated as JSON and stored in `PipelineContext.parsed_resume`

**Why LLM, not regex?** Resumes have wildly inconsistent formatting. A rule-based parser would need thousands of regex patterns to handle different layouts (tables, columns, creative designs). Gemini handles all formats with a single prompt.

**Output Example**:
```
{
  "name": "Jane Smith",
  "email": "jane@example.com",
  "skills": [
    {"name": "Python", "years": 5, "proficiency": "expert"},
    {"name": "AWS", "years": 3, "proficiency": "intermediate"}
  ],
  "experience": [
    {"title": "Senior Engineer", "company": "TechCo", "duration": "3 years", ...}
  ],
  "education": [
    {"degree": "Master's", "field": "Computer Science", "institution": "MIT", "year": 2020}
  ]
}
```

### 6.3 Stage 2 — Bias Filtering (BiasFilterAgent)

**Purpose**: Remove all personally identifiable and potentially biasing information before any evaluation.

**Critical Design Decision**: This agent uses **NO LLM**. It is entirely deterministic (regex + dictionary manipulation). This guarantees:
- Consistent anonymization every time (no LLM randomness)
- Near-instant execution (< 1ms)
- Zero API cost for this stage

**Anonymization Rules**:

| Field | Action |
|---|---|
| `name` | Replaced with `"[CANDIDATE_ID]"` |
| `email`, `phone`, `date_of_birth`, `age`, `gender`, `nationality`, `address`, `photo` | Completely removed |
| `education[].institution` | Replaced with `"[UNIVERSITY]"` |
| Pronouns in text fields (he/she/him/her/his/hers/mr./ms./mrs.) | Stripped via regex |
| Nationality/citizenship phrases | Stripped via regex |

**Why anonymize institutions?** Research shows that university name significantly biases hiring decisions. A candidate from a less-known school may be equally qualified but receives lower scores due to prestige bias. By replacing all institution names with `[UNIVERSITY]`, the scoring agent evaluates purely on degree level and field of study.

### 6.4 Stage 3 — Three Parallel Agents

After bias filtering, three independent operations run **simultaneously** using `asyncio.gather()`:

#### 6.4.1 Experience Extraction (ExperienceExtractorAgent)

**Purpose**: Verify and enrich the parsed experience data using LLM analysis.

The resume parser extracts durations as strings ("3 years" or "Jan 2019 – Mar 2021"), but these can be inaccurate. This agent:
- Reads the raw resume text to find actual date ranges
- Calculates precise `duration_months` for each position
- Computes `total_years_experience` accounting for job overlaps
- Determines `seniority_level` based on titles and total years (intern < 1yr, junior 1-3yr, mid 3-6yr, senior 6-10yr, lead 10-15yr, principal/director 15+yr)
- Maps each skill to estimated years of usage with evidence

**Why a separate agent?** The parser extracts what the resume *says*; the experience extractor verifies what the resume *means*. A candidate might list "Python" as a skill but the experience extractor traces through their job history to determine they've actually used Python for 8 years (across 3 positions), not the 5 years they self-reported.

#### 6.4.2 Graph Ingestion (GraphIngestionAgent)

**Purpose**: Decompose the parsed resume into a Knowledge Graph in Neo4j.

**Node Types Created**:
- `Candidate` — with `id` and anonymized name
- `Skill` — each unique skill (de-duplicated globally via MERGE)
- `Company` — each employer
- `Education` — degree level and field
- `Institution` — anonymized to `[UNIVERSITY]`
- `Job` — the job posting being matched against
- `SkillCluster` — auto-generated skill groupings

**Relationships Created**:
- `(Candidate)-[:HAS_SKILL {years, proficiency}]->(Skill)` — directly from parsed skills
- `(Candidate)-[:WORKED_AT {duration, title}]->(Company)` — from experience entries
- `(Candidate)-[:HAS_DEGREE]->(Education)` — from education entries
- `(Candidate)-[:STUDIED_AT]->(Institution)` — anonymized
- `(Job)-[:REQUIRES_SKILL {priority, min_years}]->(Skill)` — from job requirements
- `(Job)-[:REQUIRES_DEGREE {min_level}]->(Education)` — from job education requirements
- `(Skill)-[:IS_SIMILAR_TO {score}]->(Skill)` — auto-discovered when cosine similarity > 0.7
- `(Skill)-[:BELONGS_TO]->(SkillCluster)` — hierarchical taxonomy

**Self-Enriching Graph**: As more resumes are processed, the graph grows. Skill similarity edges (`IS_SIMILAR_TO`) are discovered automatically when the embedding agent finds two skills with vector similarity above 0.7. This means the system gets smarter over time — if it discovers that "React" and "React.js" are similar from one resume, all future candidates benefit from this knowledge.

#### 6.4.3 Embedding Generation (EmbeddingAgent)

**Purpose**: Generate a dense vector representation of the resume for semantic similarity search.

**Process**:
1. Concatenates the anonymized resume text (filtered_resume) into a single string
2. Sends it to **Google Gemini text-embedding-004** which returns a **768-dimensional vector**
3. Stores the vector in **Qdrant** with the distance metric set to **Cosine Similarity**

**Qdrant Collections**:
- `resumes` — stores resume vectors with metadata payload (resume_id, job_id, skills, experience, education)
- `job_descriptions` — stores job description vectors (created when a job is posted)

**Why vectors matter**: Keywords fail when synonyms or related concepts differ textually. "Machine Learning Engineer" and "ML Researcher" have low keyword overlap but high semantic similarity. The 768-dimensional embedding captures this meaning-level similarity.

### 6.5 Stage 4 — Hybrid Matching (HybridMatchingAgent)

**Purpose**: Combine structural graph matching with semantic vector similarity into a unified score.

This is the most algorithmically complex stage. It performs **four independent scoring signals** and fuses them with configurable weights:

#### Scoring Formula

```
hybrid_score = 0.50 × structural_score
             + 0.30 × semantic_score
             + 0.15 × experience_score
             + 0.05 × education_score
```

#### Signal 1: Structural Score (50% weight) — Neo4j Graph Traversal

Executes Cypher queries against the Neo4j knowledge graph:

- **Direct Match**: Finds skills the candidate HAS that the job REQUIRES
  ```
  MATCH (Job)-[:REQUIRES_SKILL]->(Skill)<-[:HAS_SKILL]-(Candidate)
  ```
- **Similar Match** (partial credit): If a candidate lacks a required skill but has a skill connected by `IS_SIMILAR_TO` with score > 0.7, they receive 50% credit
  ```
  MATCH (Candidate)-[:HAS_SKILL]->(similar)-[:IS_SIMILAR_TO]->(required)<-[:REQUIRES_SKILL]-(Job)
  ```

Formula: `structural_score = (direct_matches + 0.5 × similar_matches) / total_required_skills`

#### Signal 2: Semantic Score (30% weight) — Qdrant Vector Search

Retrieves the resume vector and job description vector from Qdrant, computes their **cosine similarity** (0.0 to 1.0). This captures meaning-level alignment that keyword analysis misses.

#### Signal 3: Experience Score (15% weight) — Neo4j Property Comparison

For each matched skill, compares candidate's years of experience against the job's required minimum:
```
per_skill_score = min(candidate_years / required_years, 1.0)
experience_score = average(all per_skill_scores)
```

#### Signal 4: Education Score (5% weight) — Degree Level Comparison

Maps degree levels numerically (high school=1, associate=2, bachelor=3, master=4, PhD=5) and scores:
```
education_score = min(candidate_level / required_level, 1.0)
```

### 6.6 Stage 5 — Scoring (ScoringAgent)

**Purpose**: Produce the final human-readable evaluation using all accumulated data.

The scoring agent sends a comprehensive prompt to **Gemini 2.5 Flash** containing:
- The job title, description, and requirements
- The anonymized resume (bias-filtered)
- The verified experience data (from experience extraction)
- The hybrid match results (structural, semantic, experience, education scores with matched/similar/gap skills)

The LLM is instructed to evaluate using specific weights:
- **Skills**: 40% of overall score
- **Experience**: 35% of overall score
- **Education**: 25% of overall score

**Output**:
- `overall_score` (0–100): Comprehensive candidate-job fit rating
- `skills_score` (0–100): Technical skill match quality
- `experience_score` (0–100): Work history relevance
- `education_score` (0–100): Educational background fit
- `strengths[]`: Specific advantages the candidate brings
- `gaps[]`: Areas where the candidate falls short
- `explanation`: 2-3 sentence natural language summary

**Why LLM for final scoring?** The hybrid matching agent produces numerical signals, but humans need **context**. The LLM synthesizes all data into an explanation like: *"The candidate shows strong Python expertise (8 years) matching the senior-level requirement, with relevant AWS experience. However, they lack Kubernetes experience which is listed as a must-have skill."*

### 6.7 Pipeline Context — The Shared State Object

All agents operate on a shared `PipelineContext` dataclass that accumulates results:

| Field | Set By | Used By |
|---|---|---|
| `resume_id`, `job_id` | Orchestrator (init) | All agents |
| `file_bytes`, `filename` | Upload endpoint | Parser |
| `raw_text` | Parser | Experience Extractor, Bias Filter |
| `parsed_resume` | Parser | Bias Filter, Graph Ingestion |
| `filtered_resume` | Bias Filter | Embedding, Scoring |
| `enriched_experience` | Experience Extractor | Scoring |
| `graph_node_id` | Graph Ingestion | Hybrid Matching |
| `qdrant_point_id` | Embedding | Hybrid Matching |
| `match_result` | Hybrid Matching | Scoring |
| `analysis` | Scoring | Persisted to database |
| `current_stage`, `error` | Any agent | Orchestrator error handling |

### 6.8 Orchestrator — Pipeline Controller

The `PipelineOrchestrator` coordinates execution order and handles failures:

1. **Sequential stages** (Parse → Filter) run one after another because each depends on the previous output
2. **Parallel stage** (Experience ║ Graph ║ Embed) uses `asyncio.gather()` — three tasks run concurrently since they read different fields from the context and write to different fields
3. **Non-blocking failures**: Graph Ingestion and Embedding are marked non-fatal. If Neo4j is down, the pipeline continues with reduced matching capability rather than failing entirely
4. **Status broadcasting**: Before and after each stage, the orchestrator calls a status callback that publishes events via SSE to the connected frontend

---

## 7. Database Architecture — Three-Database Strategy

RAX uses three specialized databases, each chosen for its optimal use case:

### 7.1 PostgreSQL (Supabase) — Relational Data

**Connection**: Async via `asyncpg` through SQLAlchemy ORM, using Supabase's session pooler.

**Tables**:

| Table | Purpose | Key Fields |
|---|---|---|
| `users` | Recruiter/Hiring Manager accounts | id, email, hashed_password, full_name, role |
| `jobs` | Job postings with structured requirements | id, title, description, requirements_raw (JSONB), status, created_by |
| `candidates` | Applicant records | id, name, email, phone, notification_status |
| `resumes` | Uploaded resume files with processing state | id, candidate_id, job_id, file_path, raw_text, parsed_json (JSONB), anonymized_json (JSONB), pipeline_status |
| `analyses` | Scoring results per resume | id, resume_id, job_id, overall_score, skills_score, experience_score, education_score, semantic_similarity, structural_match, explanation, strengths (JSONB), gaps (JSONB), graph_paths (JSONB) |
| `feedback` | AI-generated candidate feedback | id, candidate_id, job_id, resume_id, content, sent_at |

**Enums**:
- `UserRole`: recruiter, hiring_manager
- `JobStatus`: draft, active, closed
- `PipelineStatus`: uploaded, parsing, filtering, ingesting, embedding, matching, scoring, completed, failed
- `NotificationStatus`: not_sent, shortlisted, rejected

**Access Pattern**: The backend uses a `service_role` key (bypasses Row Level Security) for all database operations, since all access is server-side through authenticated API endpoints.

### 7.2 Neo4j (AuraDB) — Knowledge Graph

**Connection**: Async Python driver with `neo4j+ssc://` protocol (encrypted).

**Graph Schema**:

```
(Candidate {id, anonymized_name})
    -[:HAS_SKILL {years, proficiency}]-> (Skill {name, category})
    -[:WORKED_AT {duration, title}]-> (Company {name, industry})
    -[:HAS_DEGREE]-> (Education {level, field})
    -[:STUDIED_AT]-> (Institution {name})    ← always "[UNIVERSITY]"

(Job {id, title})
    -[:REQUIRES_SKILL {priority, min_years}]-> (Skill)
    -[:REQUIRES_DEGREE {min_level}]-> (Education)

(Skill) -[:IS_SIMILAR_TO {score}]-> (Skill)   ← auto-discovered
(Skill) -[:BELONGS_TO]-> (SkillCluster {name})
```

**Why Neo4j?** The hybrid matching algorithm needs to traverse multi-hop relationships: "Does the candidate have a skill SIMILAR to what the job requires?" This is a natural graph traversal that would require complex recursive SQL queries in a relational database but is a simple 2-line Cypher query in Neo4j.

### 7.3 Qdrant (Cloud) — Vector Embeddings

**Connection**: REST API over HTTPS (port 6333).

**Collections**:

| Collection | Vector Dim | Distance | Content |
|---|---|---|---|
| `resumes` | 768 | Cosine | Resume text vectors with metadata (skills, experience, education) |
| `job_descriptions` | 768 | Cosine | Job description vectors with metadata (title, required_skills) |

**Embedding Model**: Google Gemini `text-embedding-004` (768 dimensions).

**Why Qdrant?** Traditional databases cannot efficiently perform similarity search on high-dimensional vectors. Qdrant uses HNSW (Hierarchical Navigable Small World) indexing to find the nearest vectors in sub-millisecond time, even with millions of entries.

---

## 8. Frontend Architecture

### 8.1 Application Structure

The frontend is a **Single Page Application (SPA)** built with React 19 and TypeScript:

```
frontend/src/
├── App.tsx              ← Root component: routing + auth guards
├── main.tsx             ← Entry point: renders App into DOM
├── index.css            ← Global Tailwind CSS imports
├── pages/               ← Full-page route components
│   ├── LandingPage       ← Public marketing page
│   ├── LoginPage         ← Email/password authentication
│   ├── RegisterPage      ← Account creation with role selection
│   ├── DashboardPage     ← Job overview with stats
│   ├── JobListPage       ← All jobs with actions
│   ├── CreateJobPage     ← Job creation form
│   ├── JobDetailPage     ← Single job view with upload/candidate links
│   ├── UploadPage        ← Resume batch upload with real-time progress
│   ├── CandidateListPage ← Ranked candidates with scores + actions
│   ├── CandidateDetailPage ← Full analysis view with radar chart
│   └── FeedbackPage      ← AI-generated candidate feedback
├── components/
│   ├── ProcessingCard    ← 7-stage pipeline progress visualization
│   ├── RadarChart        ← 3-axis (Skills/Experience/Education) radar
│   ├── ScoreCard         ← Strengths/Gaps display cards
│   ├── ThemeProvider     ← Dark/light mode toggle
│   ├── landing/          ← Hero, Features, HowItWorks, FAQ, etc.
│   ├── layout/           ← AppShell (sidebar), ProtectedRoute
│   └── ui/               ← ConfirmDialog, NotifyModal, Toast, Spinner
├── hooks/
│   ├── useProcessingStream ← SSE client for real-time pipeline events
│   └── useApiCache         ← SWR-style data fetching with caching
├── services/             ← API client layer (Axios)
│   ├── api.ts            ← Base Axios instance with JWT interceptor
│   ├── authService.ts    ← Login, register, me
│   ├── jobService.ts     ← CRUD for jobs
│   ├── resumeService.ts  ← Upload (batch), status polling
│   ├── candidateService.ts ← List, analysis, notify
│   └── feedbackService.ts ← Generate, retrieve
├── store/
│   └── authStore.ts      ← Zustand store: token, user, auth state
└── types/
    └── index.ts          ← TypeScript interfaces for all API types
```

### 8.2 Routing

**Public Routes** (no auth required):
| Path | Page | Purpose |
|---|---|---|
| `/` | LandingPage | Marketing page with feature overview |
| `/login` | LoginPage | Authentication |
| `/register` | RegisterPage | Account creation |

**Protected Routes** (require JWT token):
| Path | Page | Purpose |
|---|---|---|
| `/app/dashboard` | DashboardPage | Active/total jobs, recent jobs list |
| `/app/jobs` | JobListPage | All job postings with status badges |
| `/app/jobs/new` | CreateJobPage | Job creation form |
| `/app/jobs/:id` | JobDetailPage | Job description + links to upload/candidates |
| `/app/upload/:jobId` | UploadPage | Drag-and-drop upload + real-time processing |
| `/app/candidates/:jobId` | CandidateListPage | Ranked candidates with scores and actions |
| `/app/candidates/:jobId/:resumeId` | CandidateDetailPage | Full analysis with radar chart |
| `/app/feedback/:id` | FeedbackPage | AI-generated candidate feedback |

### 8.3 Key UI Components

**ProcessingCard**: Displays the 7-stage pipeline progress for each resume being processed. Each stage has a colored indicator:
- **Gray** = pending (not started yet)
- **Indigo with pulse animation** = in progress
- **Green** = completed successfully
- **Red** = failed

Stages shown: Parsing → Filtering → Graph Ingestion → Embedding → Hybrid Matching → Scoring → Completed

**RadarChart**: A 3-axis radar visualization showing Skills, Experience, and Education scores (each 0–100) for a candidate. Built with Recharts. Provides an at-a-glance view of candidate strengths.

**CandidateDetailPage**: The most complex UI — displays:
- Overall score (prominent top position)
- Radar chart of all three dimension scores
- Score breakdown grid (4 cards: Skills, Experience, Education, Semantic Similarity)
- Strengths and Gaps cards side-by-side
- Full AI explanation text
- Graph paths showing how the scoring was derived

### 8.4 State Management

**Zustand** is used for global auth state (`authStore.ts`):
- `token`: JWT access token (persisted to `localStorage`)
- `user`: Decoded user object (id, email, full_name, role)
- `isAuthenticated`: Boolean derived from token presence
- `hydrate()`: Restores auth state from localStorage on page refresh

All other data (jobs, candidates, analyses) is fetched on-demand via API calls with a lightweight cache hook (`useApiCache`) that prevents duplicate requests.

---

## 9. Real-Time Communication — Server-Sent Events

### 9.1 Why SSE Over WebSockets

The pipeline status updates are **unidirectional** — only the server pushes events to the client. There is no need for the client to send data back. Server-Sent Events are the correct choice because:

| Feature | WebSocket | SSE |
|---|---|---|
| Direction | Bidirectional | Server → Client |
| Reconnection | Must implement manually | Built into browser (`EventSource` auto-reconnects) |
| Protocol | Requires upgrade handshake | Standard HTTP GET |
| Proxy compatibility | Can be blocked by intermediaries | Works through all HTTP proxies |
| Code complexity | Connection manager + ping/pong + retry logic | Simple async generator |

### 9.2 Backend Implementation

**SSE Broadcaster** (`backend/app/api/routes/sse.py`):
- Uses a **publish-subscribe pattern** with per-job subscriber queues
- Each frontend client that opens the SSE connection gets an `asyncio.Queue`
- When a pipeline agent completes a stage, the orchestrator's status callback calls `broadcaster.publish(job_id, event)`
- The publish method fan-outs the event to all queues subscribed to that job_id
- **Keepalive**: Every 15 seconds, the endpoint sends an SSE comment (`: keepalive\n\n`) to prevent proxy/browser timeouts

**Endpoint**: `GET /api/pipeline/{job_id}/events?token={jwt}`

**Event Format**:
```
data: {"resume_id": "uuid", "stage": "parsing", "status": "complete", "timestamp": "2024-01-15T10:30:00Z"}
```

### 9.3 Frontend Implementation

**`useProcessingStream` Hook**: Creates a browser `EventSource` connected to the SSE endpoint. Parses each event into a `Map<string, StageStatus>` keyed by `{resumeId}:{stageName}`. The `ProcessingCard` component reads this map to color-code each stage.

**Key Design**: The SSE connection opens **as soon as the UploadPage loads** (when the `jobId` is available), not after the upload completes. This eliminates the race condition where pipeline events fire before the frontend is listening.

---

## 10. Authentication and Authorization

### 10.1 Registration Flow

1. User submits email, password, full name, and role (recruiter or hiring_manager)
2. Backend validates email uniqueness, hashes password with **bcrypt** (via passlib)
3. Creates User record in PostgreSQL
4. Generates a **JWT token** containing `{sub: user_id, role: user_role, exp: timestamp}`
5. Returns token + user profile in the response
6. Frontend stores token in `localStorage` and sets it in Axios headers

### 10.2 Login Flow

1. User submits email + password (form-encoded per OAuth2 spec)
2. Backend looks up user, verifies password hash with bcrypt
3. Returns JWT access token
4. Frontend stores token and decodes user info

### 10.3 Request Authentication

Every protected API endpoint uses the `get_current_user` dependency:
1. Extracts `Authorization: Bearer {token}` header
2. Decodes JWT using the server's `SECRET_KEY` with HS256 algorithm
3. Looks up user by ID from the token's `sub` claim
4. Returns the authenticated User ORM object (or 401 if invalid)

### 10.4 Job Ownership

All job-related operations verify that `job.created_by == current_user.id`. A user can only see and manage their own jobs, resumes, candidates, and analyses.

---

## 11. Email Notification System

### 11.1 Dual Provider Architecture

RAX implements a **dual-provider email system** for resilience:

- **Primary (Production)**: Resend HTTP API — sends email via HTTPS POST to `api.resend.com`. Works on all hosting platforms since it uses port 443.
- **Fallback (Local Development)**: Gmail SMTP — connects via `smtplib` on port 587 with TLS. Blocked on some cloud platforms (Render) that restrict outbound SMTP ports.

**Provider Selection Logic**:
1. If `RESEND_API_KEY` is set → use Resend
2. Else if `SMTP_PASSWORD` is set → use Gmail SMTP
3. Else → return "Email service not configured" error

### 11.2 Email Templates

Two HTML email templates are generated:
- **Shortlisted**: Congratulatory email with the recruiter's custom message
- **Rejected**: Professional "unfortunately" email with encouragement and optional custom message

Both are styled HTML emails with the RAX branding.

### 11.3 Notification Flow

1. Recruiter clicks "Notify" on a candidate in the CandidateListPage
2. Modal appears with Shortlisted/Rejected toggle and optional custom message
3. Frontend calls `POST /candidates/{id}/notify` with `{type, custom_message}`
4. Backend finds the candidate's email, builds the appropriate email template
5. Sends via the active provider
6. Updates `candidate.notification_status` to `shortlisted` or `rejected`
7. Returns success/failure to frontend which shows a toast notification

---

## 12. Deployment Architecture

### 12.1 Service Mapping

```
┌───────────────┐     HTTPS      ┌─────────────────┐
│   Browser     │ ◄────────────► │   Vercel CDN    │
│   (User)      │                │   (Frontend)    │
│               │                │   React SPA     │
└───────┬───────┘                └─────────────────┘
        │ HTTPS
        ▼
┌─────────────────┐
│   Render         │
│   (Backend)      │
│   FastAPI +      │
│   Uvicorn        │
│                  │
│ Connects to:     │
│  • Supabase PG   │    ← PostgreSQL (port 5432)
│  • Neo4j AuraDB  │    ← Bolt protocol (port 7687, encrypted)
│  • Qdrant Cloud  │    ← HTTPS (port 6333)
│  • Supabase Stor │    ← HTTPS (storage API)
│  • Resend API    │    ← HTTPS (port 443)
└─────────────────┘
```

### 12.2 Environment Variables (Production)

| Variable | Service | Purpose |
|---|---|---|
| `DATABASE_URL` | Supabase | PostgreSQL connection string via session pooler |
| `SUPABASE_URL` | Supabase | Storage API base URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase | Admin-level access (bypasses RLS) |
| `NEO4J_URI` | AuraDB | Graph database connection endpoint |
| `NEO4J_USERNAME` / `NEO4J_PASSWORD` | AuraDB | Graph database authentication |
| `QDRANT_URL` / `QDRANT_API_KEY` | Qdrant Cloud | Vector database connection + auth |
| `GOOGLE_API_KEY` | Google AI | Gemini LLM and embedding API key |
| `SECRET_KEY` | Backend | JWT signing secret |
| `CORS_ORIGINS` | Backend | Allowed frontend domains (comma-separated) |
| `ENVIRONMENT` | Backend | `development` or `production` |
| `RESEND_API_KEY` | Resend | Email delivery API key |
| `EMAIL_FROM` | Resend | Sender address for emails |
| `VITE_API_URL` | Frontend (Vercel) | Backend API base URL for production |

### 12.3 Free Tier Utilization

Every external service uses a free tier:
- **Supabase**: Free tier (500MB database, 1GB storage)
- **Neo4j AuraDB**: Free instance (limited nodes/relationships)
- **Qdrant Cloud**: Free tier (1GB vector storage)
- **Render**: Free tier (auto-sleep after 15 min inactivity)
- **Vercel**: Free tier (100GB bandwidth/month)
- **Google Gemini**: Free tier API calls (rate-limited)
- **Resend**: Free tier (100 emails/day, sandbox domain)

---

## 13. Concurrency and Performance Optimizations

### 13.1 Pipeline-Level Concurrency

A **semaphore** limits concurrent pipeline executions to **3** (`_PIPELINE_CONCURRENCY = 3`). When a batch of 20 resumes is uploaded, only 3 run their pipelines simultaneously. The remaining 17 queue and start as slots free up. This prevents overwhelming the Gemini API rate limits and database connection pools.

### 13.2 LLM-Level Concurrency

A separate **Gemini semaphore** (limit 3) in `base_agent.py` wraps all `call_llm()` and `embed_text()` calls. Even within a single pipeline, the three parallel agents (Experience + Graph + Embed) coordinate their Gemini API calls through this semaphore to stay within rate limits.

### 13.3 Parallel Stage Execution

Stages 3a/3b/3c (Experience Extraction, Graph Ingestion, Embedding) run concurrently via `asyncio.gather()`:
- Experience Extraction uses the LLM (reads raw_text, writes enriched_experience)
- Graph Ingestion writes to Neo4j (reads parsed_resume, writes graph_node_id)
- Embedding calls the embedding API + writes to Qdrant (reads filtered_resume, writes qdrant_point_id)

Since these agents read/write different fields and talk to different services, parallelization is safe and reduces total pipeline time by approximately 40-60%.

### 13.4 Deterministic Bias Filter

The bias filter was deliberately made **LLM-free** (regex-only). This eliminated one LLM call per pipeline, reduced cost, and made the filtering stage complete in under 1 millisecond instead of 2-3 seconds.

### 13.5 Batch Upload

The batch upload endpoint (`POST /resumes/upload/batch`) accepts up to 20 files in a single HTTP request. All database inserts happen first (single transaction), then all pipeline tasks are spawned concurrently. This avoids the overhead of 20 separate HTTP round-trips.

---

## 14. Bias Prevention Strategy

RAX implements a **multi-layered** approach to bias prevention:

### Layer 1: Pre-Scoring Anonymization
Before any scoring occurs, the BiasFilterAgent strips:
- **Names** → `[CANDIDATE_ID]` (prevents name-based ethnic/gender bias)
- **Email/Phone** → removed (prevents socioeconomic inference)
- **University Names** → `[UNIVERSITY]` (prevents prestige bias)
- **Gender Pronouns** → stripped from all text
- **Nationality/Citizenship** → stripped from all text

### Layer 2: Structured Evaluation
The scoring agent evaluates candidates on measurable dimensions:
- Skills: compared against explicit job requirements
- Experience: verified years and relevance, not just employer names
- Education: degree level and field, not institution reputation

### Layer 3: Graph-Based Objectivity
The Neo4j knowledge graph creates an objective skill topology. A candidate is scored on whether they *have* the required skill (or a similar one), not on how impressively they described it. A candidate from a bootcamp who genuinely knows Python scores the same as an MIT graduate who knows Python.

---

## 15. Explainability and Transparency

Unlike black-box ATS systems, RAX provides full transparency:

### 15.1 Score Decomposition
Every candidate receives not just an overall score, but four independent dimensional scores:
- **Skills Score** (0–100): How well does the candidate's skillset match the job requirements?
- **Experience Score** (0–100): How relevant and extensive is their work history?
- **Education Score** (0–100): Does their academic background align?
- **Semantic Similarity** (0–1): How semantically similar is the entire resume to the job description?

### 15.2 Natural Language Explanation
The scoring agent generates a 2-3 sentence explanation like:
*"Strong Python and AWS expertise with 8 years of relevant experience. The candidate shows deep knowledge of cloud infrastructure matching the senior-level requirement. However, they lack Kubernetes experience, which is listed as a must-have skill."*

### 15.3 Graph Paths
The analysis includes traceable graph paths showing exactly how matching occurred:
```
Candidate -[:HAS_SKILL]-> Python <-[:REQUIRES_SKILL]- Job
Candidate -[:HAS_SKILL]-> Docker -[:IS_SIMILAR_TO {0.72}]-> Kubernetes <-[:REQUIRES_SKILL]- Job
```

### 15.4 Strengths and Gaps
Concrete lists of matched strengths and identified gaps, directly tied to job requirements.

---

## 16. Complete Data Flow — End to End

### Step 1: Recruiter Creates a Job Posting
```
Frontend: CreateJobPage → POST /api/jobs
Backend: Creates Job in PostgreSQL → Ingests into Neo4j (Skill nodes) → Embeds in Qdrant
```

### Step 2: Recruiter Uploads Resumes
```
Frontend: UploadPage (drag-and-drop) → POST /api/resumes/upload/batch (multipart FormData)
Backend: Stores files in Supabase Storage → Creates Candidate + Resume records in PostgreSQL
         → Spawns async pipeline tasks (limited to 3 concurrent)
```

### Step 3: Pipeline Processes Each Resume
```
For each resume (up to 3 in parallel):
  1. PARSE: Extract text → Gemini LLM → structured JSON
  2. FILTER: Anonymize name, institution, pronouns (instant, no LLM)
  3. PARALLEL:
     a. EXPERIENCE: Gemini verifies dates/durations → enriched experience data
     b. GRAPH: Create Neo4j nodes/edges from parsed data
     c. EMBED: Gemini embedding → 768d vector → Qdrant storage
  4. MATCH: Neo4j graph traversal + Qdrant cosine similarity → hybrid score
  5. SCORE: Gemini evaluates all data → multi-dimensional score + explanation

  After each stage: SSE event → Frontend ProcessingCard updates in real-time
```

### Step 4: Recruiter Reviews Candidates
```
Frontend: CandidateListPage → GET /api/jobs/{id}/candidates?sort_by=overall_score
Backend: Joins Candidate + Resume + Analysis tables → returns ranked list with scores
Frontend: Displays sortable table with score badges and notification status
```

### Step 5: Recruiter Views Detailed Analysis
```
Frontend: CandidateDetailPage → GET /api/resumes/{id}/analysis
Backend: Returns full Analysis record (all scores, strengths, gaps, graph paths, explanation)
Frontend: Renders radar chart + score cards + explanation text
```

### Step 6: Recruiter Sends Notifications
```
Frontend: NotifyModal → POST /api/candidates/{id}/notify
Backend: Builds HTML email template → Sends via Resend/SMTP → Updates notification_status
Frontend: Shows success/error toast, notification badge updates
```

### Step 7: Recruiter Generates Feedback
```
Frontend: FeedbackPage → POST /api/feedback/{candidateId}/{jobId}
Backend: Gemini generates personalized feedback based on analysis → Stores in PostgreSQL
Frontend: Displays formatted feedback text with copy button
```

---

## 17. API Endpoint Reference

### Authentication
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create account (email, password, name, role) |
| POST | `/api/auth/login` | Authenticate (returns JWT) |
| GET | `/api/auth/me` | Get current user profile |

### Jobs
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/jobs` | List jobs owned by current user |
| POST | `/api/jobs` | Create job (triggers Neo4j + Qdrant ingestion) |
| GET | `/api/jobs/{id}` | Get single job |
| PUT | `/api/jobs/{id}` | Update job |
| DELETE | `/api/jobs/{id}` | Delete job + cascade |

### Resumes
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/resumes/upload` | Upload single resume (triggers pipeline) |
| POST | `/api/resumes/upload/batch` | Upload up to 20 resumes at once |
| GET | `/api/resumes/{id}/status` | Check pipeline processing status |
| DELETE | `/api/resumes/{id}` | Delete resume |

### Candidates & Analysis
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/jobs/{id}/candidates` | List candidates with scores (sortable, filterable) |
| GET | `/api/resumes/{id}/analysis` | Full analysis breakdown |

### Feedback
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/feedback/{candidateId}/{jobId}` | Generate AI feedback |
| GET | `/api/feedback/{id}` | Retrieve generated feedback |

### Notifications
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/candidates/{id}/notify` | Send shortlisted/rejected email |

### Real-Time
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/pipeline/{jobId}/events` | SSE stream for pipeline status updates |

---

## 18. Local Development Setup

### Prerequisites
- Python 3.14+
- Node.js 18+
- Docker (for local Neo4j + Qdrant, optional)

### Backend Setup
```
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create `backend/.env` with all required environment variables (see Section 12.2).

```
alembic upgrade head           # Run database migrations
uvicorn app.main:app --reload --port 8002
```

### Frontend Setup
```
cd frontend
npm install
npm run dev                    # Starts Vite dev server on port 5173
```

The Vite dev server proxies `/api` requests to `http://localhost:8002` automatically.

### Optional: Local Neo4j + Qdrant
```
docker-compose up -d           # Starts Neo4j (7475/7688) + Qdrant (6333/6334)
```

Update `.env` to point at localhost instances instead of cloud services.

### Production Build
```
cd frontend
npm run build                  # Outputs to dist/ — deploy to Vercel
```

---

*Document prepared for academic review — RAX Project, April 2026*
