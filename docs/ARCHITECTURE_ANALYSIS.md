# RAX — Architecture & Scoring Analysis

## Table of Contents

1. [Why Qdrant?](#1-why-qdrant)
2. [Why Neo4j?](#2-why-neo4j)
3. [How We Use Qdrant & Neo4j Together](#3-how-we-use-qdrant--neo4j-together)
4. [How We Use Supabase](#4-how-we-use-supabase)
5. [How the Resume Score Is Calculated](#5-how-the-resume-score-is-calculated)
6. [Additional Features Possible with the Existing Setup](#6-additional-features-possible-with-the-existing-setup)

---

## 1. Why Qdrant?

### The Problem

Keyword matching fails in hiring. A job listing asking for "machine learning" should also match candidates who describe their work as "deep learning," "statistical modeling," or "predictive analytics." Traditional database queries cannot capture this semantic relationship between terms.

### Why Qdrant Solves This

Qdrant is a purpose-built vector database that stores **meaning** as numerical vectors, not just text. When a resume and a job description are converted into 768-dimensional vectors (via Google Gemini embeddings), Qdrant can measure how semantically close they are — even when zero words overlap.

### Why Not Alternatives?

| Consideration | Qdrant | Pinecone | pgvector (Postgres extension) |
|---|---|---|---|
| Self-hosted & free | Yes | No (SaaS) | Yes |
| Rich payload storage | Yes — full JSON payloads per vector | Limited metadata | Basic |
| Filtering + search in one query | Native payload filters | Supported | Clumsy with SQL joins |
| Collection isolation | Separate collections for resumes vs. jobs | Namespaces | Same table, filtered |
| Performance at scale | Purpose-built HNSW indexing | Excellent | Degrades with table size |

Qdrant was chosen because it is **self-hosted** (no vendor lock-in, runs in Docker alongside the stack), supports **rich payload storage** (we attach full resume content, skills, experience, and education directly to each vector point), and provides **native cosine similarity scoring** out of the box.

### What We Store in Qdrant

**Two collections:**

- **`resumes`** — One vector per resume. Each point contains the 768-dim embedding of the resume text plus a rich payload: the full concatenated resume text, structured skills with years and proficiency, experience entries with titles and companies, and education records. This means a semantic query returns not just a similarity score but the full candidate context.

- **`job_descriptions`** — One vector per job. Each point contains the embedding of the job description text plus the job title, full description, and required skills list.

---

## 2. Why Neo4j?

### The Problem

Hiring decisions are inherently about **relationships**: Does this candidate have the skills this job requires? How many years? Are they missing a key skill, or do they have something closely related? These are graph traversal questions that relational databases answer slowly with multi-table JOINs.

### Why Neo4j Solves This

Neo4j is a native graph database where relationships are first-class citizens, not computed at query time via joins. Traversing from a Job node through REQUIRES_SKILL to Skill nodes and back through HAS_SKILL to a Candidate node is a single, indexed operation — not a cascade of table scans.

### The Knowledge Graph We Build

The following entities and relationships are created:

**Nodes:**
- **Candidate** — Represents a person (with anonymized name for bias-free evaluation)
- **Job** — A job posting with title
- **Skill** — A specific technology, tool, or competency (e.g., "Python," "Project Management")
- **Company** — An employer
- **Education** — A degree level and field (e.g., Master's in Computer Science)
- **Institution** — A university or college

**Relationships:**
- Candidate **HAS_SKILL** Skill (with properties: years of experience, proficiency level)
- Candidate **WORKED_AT** Company (with properties: duration, job title held)
- Candidate **HAS_DEGREE** Education
- Candidate **STUDIED_AT** Institution
- Job **REQUIRES_SKILL** Skill (with properties: priority level, minimum years required)
- Job **REQUIRES_DEGREE** Education (with property: minimum degree level)
- Skill **IS_SIMILAR_TO** Skill (with property: similarity score, threshold > 0.7)

### Why This Graph Matters for Scoring

The graph enables three queries that would be extremely expensive in SQL:

1. **Direct skill matching** — In one traversal: start at Job, follow REQUIRES_SKILL to all required Skills, reverse-follow HAS_SKILL back to Candidate. Result: every required skill the candidate possesses, with their years vs. required years.

2. **Similar skill matching** — When a candidate doesn't have an exact required skill, traverse through IS_SIMILAR_TO to find related skills they do have. A candidate with "PyTorch" partially satisfies a "TensorFlow" requirement if the similarity score is above 0.7.

3. **Skill gap identification** — All required skills that are neither directly matched nor similarly matched are identified as gaps in a single pass.

---

## 3. How We Use Qdrant & Neo4j Together

The two databases serve complementary roles in a **hybrid matching** strategy:

| Aspect | Neo4j (Structural) | Qdrant (Semantic) |
|---|---|---|
| What it measures | Explicit skill overlap, years of experience match, degree level | Overall meaning similarity between resume and job description |
| Strength | Precise, explainable ("Candidate has 5/7 required skills") | Catches intent that keywords miss ("data scientist" ≈ "ML engineer") |
| Weakness | Misses related skills not in the graph | Cannot explain why two things are similar |
| Output | Structural score + matched/similar/gap lists + graph paths | Cosine similarity score (0.0 – 1.0) |

**Hybrid fusion formula:**

$$\text{hybrid\_score} = 0.50 \times \text{structural} + 0.30 \times \text{semantic} + 0.15 \times \text{experience} + 0.05 \times \text{education}$$

The structural (Neo4j) component is weighted highest at 50% because explicit skill matching is the most reliable signal. Semantic similarity (Qdrant) at 30% captures broader alignment. Experience and education scores from graph traversal contribute the remaining 20%.

**Both systems are non-fatal.** If Neo4j or Qdrant are unavailable, the pipeline falls back to default scores (0.5) and relies more heavily on the LLM-based scoring stage, which independently evaluates the resume against the job description.

---

## 4. How We Use Supabase

Supabase serves two distinct roles in the architecture:

### 4a. PostgreSQL Database (via Supabase)

The primary relational database stores all structured application data:

- **Users** — Authentication, roles (recruiter, hiring manager)
- **Jobs** — Title, description, requirements (as JSON), status
- **Candidates** — Name, email, phone, linked Neo4j node ID
- **Resumes** — File path reference, raw text, parsed JSON, anonymized JSON, pipeline status, Qdrant point ID
- **Analyses** — All scores (overall, skills, experience, education), semantic similarity, structural match, explanation text, strengths, gaps, graph paths

The application connects via **SQLAlchemy async** with the **asyncpg** driver, maintaining a connection pool of 10 connections with 20 overflow for concurrent pipeline processing.

### 4b. Object Storage (Supabase Storage)

Resume files (PDF, DOCX) are stored in a Supabase Storage bucket named `resumes`. The upload path follows the pattern `resumes/{candidate_id}/{filename}`, ensuring files are organized per candidate.

The storage is **best-effort** — if the upload to Supabase Storage fails, the pipeline still proceeds because the file bytes are already extracted into raw text during parsing. The stored file serves as an archival reference, not a runtime dependency.

### 4c. Authentication

JWT-based authentication via Supabase Auth. Access tokens expire after 60 minutes. Role-based access control restricts job creation to recruiters and hiring managers.

---

## 5. How the Resume Score Is Calculated

The scoring pipeline has 7 stages, each building on the output of the previous one.

### Stage 1 — Resume Parsing

The uploaded file (PDF or DOCX) is converted to raw text. This text is sent to Google Gemini, which extracts structured data: candidate name, email, phone, skills (with years and proficiency), work experience (title, company, duration, description), and education (degree, field, institution, year).

### Stage 1b — Experience Verification (LLM Judge)

An independent LLM call re-reads the raw resume text specifically to verify and correct experience information. This "judge" agent:

- Calculates **total years of experience** by identifying actual date ranges (e.g., "Jan 2019 – Present") and summing distinct employment periods
- Determines **seniority level** from job titles and total experience (intern → junior → mid → senior → lead → principal/director)
- Estimates **per-skill years** based on when each skill first appeared across experience entries
- Corrects duration values that the initial parser may have gotten wrong

This step exists because experience extraction from resumes is notoriously inaccurate — the initial parser often misreads durations or defaults skills to 0 years. A dedicated verification pass dramatically improves experience scoring accuracy.

### Stage 2 — Bias Filtering

Before any evaluation, the parsed resume is anonymized:
- Name replaced with "[CANDIDATE_ID]"
- Institution names replaced with "[UNIVERSITY]"
- Gender indicators removed (pronouns, Mr./Ms./Mrs.)
- Nationality and ethnicity signals removed
- Age indicators removed (dates of birth, graduation years)

All skills, experience detail, and education levels are preserved. The filtered resume is what flows into all downstream evaluation — ensuring the scoring system never sees identity information.

### Stage 3a — Graph Ingestion (parallel)

The parsed resume is ingested into Neo4j as a Candidate node with relationships to Skills, Companies, Education levels, and Institutions. This builds the knowledge graph used for structural matching.

### Stage 3b — Vector Embedding (parallel)

The resume text is embedded into a 768-dimensional vector via Google Gemini and stored in Qdrant with the full resume content as payload.

*Stages 3a and 3b run in parallel to minimize pipeline latency.*

### Stage 4 — Hybrid Matching

Neo4j and Qdrant are queried simultaneously:

**From Neo4j:**
- Count of directly matched skills vs. total required skills → **structural score**
- Skills matched via similarity relationships (partial credit at 50%) → incorporated into structural score
- Per-skill years ratio (candidate years / required years, capped at 1.0) → **experience score**
- Degree level comparison → **education score**

**From Qdrant:**
- Cosine similarity between resume vector and job description vector → **semantic score**

These four sub-scores are fused into a single hybrid score using the weighted formula.

### Stage 5 — LLM Scoring (Final)

The LLM (Gemini) receives everything collected so far:
- The full job title, description, and requirements
- The anonymized resume (structured)
- The verified experience data (total years, seniority, per-skill breakdown)
- The hybrid match data (graph paths, matched skills, semantic similarity)

It produces final scores on a 0–100 scale:

| Component | Weight | What It Measures |
|---|---|---|
| **Skills Score** | 40% | How many required skills the candidate has, with consideration for years of experience per skill |
| **Experience Score** | 35% | Total years, seniority level, domain relevance to the job description |
| **Education Score** | 25% | Degree level and field alignment with job requirements |

$$\text{overall\_score} = 0.40 \times \text{skills} + 0.35 \times \text{experience} + 0.25 \times \text{education}$$

The LLM is instructed to use the verified experience data as the **authoritative source** for experience assessment and to base its evaluation **primarily** on direct resume-vs-job comparison — the hybrid match data is supplementary context, not the sole input.

The final output includes: overall score, individual component scores, a list of strengths, a list of gaps, and a 2-3 sentence natural language explanation.

### Why Two Scoring Layers?

The hybrid matching (Stage 4) provides **mechanistic, deterministic scores** — they're reproducible and explainable through graph paths. The LLM scoring (Stage 5) provides **holistic, contextual judgment** — it can interpret nuance that rule-based matching misses (e.g., recognizing that "led a team of 12 engineers" implies strong leadership even if "leadership" isn't listed as a skill).

The combination of both layers makes the scoring both **explainable** (via graph paths) and **accurate** (via LLM judgment).

---

## 6. Additional Features Possible with the Existing Setup

The following features require **no new infrastructure** — they use the databases, agents, and pipeline already in place.

### 6.1 Candidate Comparison View

**What:** Side-by-side comparison of 2-3 candidates for the same job, showing skill overlaps, gaps, and score breakdowns.

**How:** The analysis table already stores per-component scores, strengths, and gaps for each resume. A new frontend page can query analyses by job_id, sort by overall_score, and render a comparison grid. No backend changes needed beyond a simple aggregation endpoint.

### 6.2 Job-to-Candidate Recommendations

**What:** When a new job is created, automatically surface the top N existing candidates from the Qdrant resume collection who are most similar.

**How:** The `job_descriptions` and `resumes` Qdrant collections already exist. Embed the job description, query the `resumes` collection with that vector, and return the top matches with their payloads (which already contain full resume data). This is a single `query_points()` call.

### 6.3 Skill Gap Reports per Job

**What:** Aggregate across all candidates for a job: "80% of candidates lack Kubernetes experience" or "Average Python experience is 3.2 years vs. 5 years required."

**How:** The Neo4j graph already stores HAS_SKILL relationships with years and all REQUIRES_SKILL relationships with min_years. A Cypher query aggregating across all Candidates linked to a Job via their resumes produces this report directly.

### 6.4 Similar Candidate Discovery

**What:** Given a strong candidate, find other candidates in the system with similar profiles.

**How:** Retrieve the candidate's vector from the Qdrant `resumes` collection and query for nearest neighbors. The rich payloads return full resume context for each match. Combine with Neo4j traversal to show which specific skills overlap.

### 6.5 Resume Improvement Suggestions

**What:** After scoring, tell the candidate specifically what to add to their resume to improve their match.

**How:** The analysis already contains `skill_gaps` (from Neo4j traversal) and `gaps` (from LLM analysis). Combine these with the job requirements to generate a targeted suggestion like: "Adding Kubernetes experience (required: 2+ years) and obtaining AWS certification would improve your match from 67% to an estimated 85%."

### 6.6 Batch Re-scoring on Job Requirement Changes

**What:** When a recruiter updates job requirements, automatically re-score all existing candidates.

**How:** The pipeline already supports re-running scoring for existing resumes — the parsed and anonymized JSON are stored in the resumes table, and the enriched experience is reproducible. A backend task can iterate over resumes for a job, reload context from stored data, and re-run stages 4-5 without re-parsing or re-embedding.

### 6.7 Recruiter Calibration Dashboard

**What:** Show recruiters how their hiring decisions correlate with RAX scores over time. Did they hire candidates who scored high? Did rejected candidates have low scores?

**How:** Add a `hired` boolean or `outcome` enum to the candidate/analysis model. Over time, this builds a calibration dataset. Display correlation between RAX overall_score and actual hiring outcomes as a chart. This requires only one new column and a frontend visualization.

### 6.8 Multi-Job Candidate Routing

**What:** When a candidate doesn't match well for the job they applied to, automatically suggest other open jobs they'd be strong for.

**How:** Take the candidate's vector from the `resumes` collection and query the `job_descriptions` collection. The top-scoring jobs (excluding the one they applied for) are recommendations. Payloads already contain job titles and descriptions for display.

### 6.9 Skill Trend Analytics

**What:** Dashboard showing which skills are most common across candidates, which are rarest, and how they trend over time.

**How:** Neo4j already has all Skill nodes with HAS_SKILL relationships. A Cypher aggregation query (`MATCH (s:Skill)<-[:HAS_SKILL]-(c:Candidate) RETURN s.name, count(c) ORDER BY count(c) DESC`) provides this data instantly. Add a `created_at` property to track trends over time.

### 6.10 Explainable Score Drilldown

**What:** When a recruiter clicks on a score, show the graph traversal path visually — "Candidate has Python (5yr) → Job requires Python (3yr) ✓" with a mini graph visualization.

**How:** The `graph_paths` array is already stored in the analysis table. These are human-readable path strings like "Candidate -[:HAS_SKILL]-> Python <-[:REQUIRES_SKILL]- Job". A frontend component can parse these into a visual node-edge diagram without any backend changes.
