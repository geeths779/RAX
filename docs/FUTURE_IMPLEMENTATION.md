# RAX — Future Implementation Roadmap

Every feature below includes a **difficulty tag** reflecting the estimated engineering effort given the current RAX architecture (FastAPI + SQLAlchemy async, React frontend, Google GenAI SDK, Qdrant, Neo4j, Supabase).

| Tag | Meaning |
|---|---|
| **EASY** | Can be built in a day. Uses existing endpoints, models, or simple frontend additions. No new infrastructure. |
| **MEDIUM** | Requires a new backend module or significant frontend work, but stays within the existing stack. 2–4 days. |
| **HARD** | Needs new infrastructure, third-party integrations, or complex multi-system coordination. 1–2 weeks. |

---

## New Features

### 1. Candidate Email Notification Service — `MEDIUM`

**What it does:**
After a recruiter reviews candidates, they can select candidates from the list and trigger one of two email actions:

- **Shortlisted** — Sends a congratulations email informing the candidate they have been shortlisted and will receive a call from the hiring team. The recruiter can customize the message body before sending.
- **Rejected** — Sends a constructive email thanking the candidate, providing personalized feedback on areas for improvement (drawn from the analysis gaps and skill gaps already stored), and wishing them well for future opportunities.

**How it fits the existing architecture:**
- The candidate's email is already captured during resume parsing and stored in the `candidates` table.
- The analysis table already stores `gaps`, `skill_gaps`, and `explanation` — these can be templated directly into the rejection email without any additional LLM call.
- The recruiter provides a custom message or uses a default template. The backend composes the email body by merging the template with analysis data.

**Implementation approach:**
- Add an email utility module using a transactional email provider (Resend, SendGrid, or Supabase's built-in email via Auth). All three have Python SDKs.
- Add a POST endpoint: `/api/candidates/{candidate_id}/notify` accepting `{ "type": "shortlisted" | "rejected", "custom_message": "..." }`.
- For rejected candidates, auto-populate the email with the top 3 gaps from the analysis and a summary of missing skills from the Neo4j skill_gaps.
- Add a "Notify" dropdown button (Shortlisted / Rejected) in the CandidateListPage with an optional message preview modal.

**Why MEDIUM, not EASY:**
Email delivery requires choosing and configuring a provider, handling delivery failures gracefully, and building the recruiter-facing message preview/edit UI. The backend logic itself is straightforward since all the data already exists.

---

### 2. Resume Preview on Candidate Detail Page — `EASY`

**What it does:**
Adds a "Preview Resume" button on the candidate detail page that opens the original uploaded PDF/DOCX in a viewer — either inline in the page or in a new browser tab.

**How it fits the existing architecture:**
- Resume files are already stored in Supabase Storage at the path `resumes/{candidate_id}/{filename}`.
- The `resumes` table stores `file_path` which maps directly to the Supabase Storage path.
- Supabase Storage supports generating signed URLs for secure, time-limited access to private files.

**Implementation approach:**
- Add a GET endpoint: `/api/resumes/{resume_id}/preview` that generates a signed URL from Supabase Storage (using `storage.from_("resumes").create_signed_url(path, expires_in=3600)`) and returns it.
- On the frontend CandidateDetailPage, add a button that calls this endpoint and opens the signed URL in a new tab or renders it inline using the browser's native PDF viewer (`<iframe>` or `<embed>`).
- For DOCX files, either convert to PDF server-side (using python-docx + reportlab) or open as a download.

**Why EASY:**
Supabase Storage already has the file. Generating a signed URL is one SDK call. The frontend change is a single button with a link.

---

### 3. Social Profile Enrichment via Google Search Grounding — `HARD`

**What it does:**
Uses the Google Gemini API's **Grounding with Google Search** tool to look up a candidate's LinkedIn profile and GitHub activity based on their name, email, or other resume details. The results add a social/personality dimension to the candidate profile:

- LinkedIn: current headline, connection count indicator, endorsements, recent activity themes
- GitHub: public repository count, primary languages, contribution frequency, notable projects

This data is presented as a supplementary "Social Profile" section in the candidate detail view. It has minimal effect on the overall score (suggested weight: 5% of overall, subtracted equally from skills and experience) but gives recruiters personality and activity context.

**How Google Search Grounding works (from the Gemini API docs):**
The `google_search` tool is passed alongside the prompt. Gemini automatically decides whether to search, generates one or more search queries, processes the results, and returns a grounded response with `groundingMetadata` containing `webSearchQueries`, `groundingChunks` (source URLs with titles), and `groundingSupports` (text segments linked to specific sources). This is supported on Gemini 2.5 Flash (our current model) and newer.

**Implementation approach:**
- Create a new `SocialProfileAgent` that runs in the pipeline after parsing (parallel with bias filter — it uses the original name/email, not the anonymized version).
- The agent calls Gemini with `google_search` tool enabled and a prompt like: "Find the LinkedIn profile and GitHub profile for [candidate name] [candidate email]. Summarize their professional headline, key endorsements, GitHub repositories, and primary programming languages. Return structured JSON."
- The grounded response includes cited URLs (LinkedIn profile link, GitHub profile link) that can be displayed directly.
- Store the result in a new `social_profile` JSONB column on the `candidates` table.
- Display on the CandidateDetailPage as a collapsible "Social Profile" card with links to source profiles.

**Privacy and ethical considerations:**
- Only public information is retrieved (Google Search results are public by definition).
- The social data is shown to recruiters as supplementary context, not used as a primary scoring factor.
- Candidates should be informed in the application process that public profile information may be reviewed.
- The bias filter does NOT anonymize social data — it is shown separately from the scored resume to maintain the bias-free scoring pipeline.

**Why HARD:**
- Google Search Grounding is billed per search query (multiple queries per candidate = cost at scale).
- Name-to-profile matching is inherently noisy — "John Smith" returns thousands of profiles. Disambiguation requires combining name + email domain + skills + location.
- Rate limiting and error handling for the Search tool need careful implementation.
- Privacy/compliance review may be required depending on jurisdiction (GDPR, etc.).
- The frontend needs a new UI section with external link handling.

---

## Existing Architecture Features (from Architecture Analysis)

These features were identified in the architecture analysis document as achievable with the current infrastructure. They are repeated here with difficulty tags for roadmap planning.

---

### 4. Candidate Comparison View — `EASY`

**What it does:**
Side-by-side comparison of 2–3 candidates for the same job, showing skill overlaps, gaps, and score breakdowns in a comparison grid.

**Why EASY:** The analysis table already stores all per-component scores, strengths, and gaps. This is purely a frontend page that queries existing data and renders it as a comparison table. No new backend logic needed beyond a simple list endpoint filtered by job_id (which already exists).

---

### 5. Job-to-Candidate Recommendations — `EASY`

**What it does:**
When a new job is created, automatically surface the top N existing candidates from the Qdrant resume collection who are the best semantic match.

**Why EASY:** The `resumes` and `job_descriptions` Qdrant collections already exist with rich payloads. This is a single `query_points()` call using the job's vector against the resumes collection. The payload returns full candidate context. One new endpoint + one frontend card.

---

### 6. Skill Gap Reports per Job — `EASY`

**What it does:**
Aggregate view across all candidates for a job: "80% of candidates lack Kubernetes experience," "Average Python experience is 3.2 years vs. 5 years required."

**Why EASY:** Neo4j already has all the data — HAS_SKILL with years, REQUIRES_SKILL with min_years. A single Cypher aggregation query produces the report. One new endpoint + one frontend dashboard widget.

---

### 7. Similar Candidate Discovery — `EASY`

**What it does:**
Given a strong candidate, find other candidates in the system with similar profiles using vector similarity.

**Why EASY:** Retrieve the candidate's vector from Qdrant, query for nearest neighbors. Rich payloads return full context. Combine with a Neo4j traversal for skill overlap detail. One endpoint + one frontend section.

---

### 8. Resume Improvement Suggestions — `MEDIUM`

**What it does:**
After scoring, generate a targeted report telling the candidate exactly what to add to their resume to improve their match score.

**Why MEDIUM:** The raw data exists (skill_gaps, gaps, requirements). But generating a polished, actionable improvement report requires an additional LLM call with a carefully crafted prompt that maps gaps to specific, constructive suggestions. Also needs a new frontend view to present the suggestions and potentially integrate with the email notification service (Feature 1) to send improvement feedback to rejected candidates.

---

### 9. Batch Re-scoring on Job Requirement Changes — `MEDIUM`

**What it does:**
When a recruiter updates job requirements, automatically re-score all existing candidates for that job without re-uploading resumes.

**Why MEDIUM:** The parsed JSON, anonymized JSON, and enriched experience are all stored in the database. Re-running stages 4–5 (Hybrid Matching + Scoring) is technically straightforward. The complexity is in the orchestration: iterating over potentially many resumes, managing concurrent LLM calls, handling partial failures, and updating the UI in real-time as scores refresh. Also needs a "Re-score All" button with progress indication.

---

### 10. Recruiter Calibration Dashboard — `MEDIUM`

**What it does:**
Show recruiters how their past hiring decisions correlate with RAX scores. Did they hire high-scorers? Did low-scorers get rejected? Over time, this builds confidence in the scoring system.

**Why MEDIUM:** Requires adding an outcome tracking column (`hired`, `rejected`, `interviewing`) to the candidate/analysis model, building a data collection workflow (recruiter marks outcomes over time), and creating a visualization dashboard with correlation charts. The database change is trivial, but the UX for outcome tracking and the analytics visualization require meaningful frontend effort.

---

### 11. Multi-Job Candidate Routing — `EASY`

**What it does:**
When a candidate doesn't match well for their applied job, automatically suggest other open jobs they would be strong for.

**Why EASY:** Take the candidate's vector from the `resumes` collection, query the `job_descriptions` collection with it. Top matches (excluding current job) are recommendations. Payloads already contain job titles and descriptions. One new endpoint + one frontend "Other Jobs You'd Match" card.

---

### 12. Skill Trend Analytics — `MEDIUM`

**What it does:**
Dashboard showing which skills are most common across candidates, which are rarest, and how supply/demand trends shift over time.

**Why MEDIUM:** The Cypher aggregation query is simple (`MATCH (s:Skill)<-[:HAS_SKILL]-(c) RETURN s.name, count(c)`). But building a meaningful trend dashboard requires timestamp tracking on skill relationships, time-series aggregation logic, and a frontend charting component (e.g., Recharts or Chart.js). The backend is easy; the frontend visualization is the bulk of the work.

---

### 13. Explainable Score Drilldown — `MEDIUM`

**What it does:**
When a recruiter clicks on a score component, show the Neo4j graph traversal path visually — "Candidate has Python (5yr) → Job requires Python (3yr) ✓" rendered as interactive nodes and edges.

**Why MEDIUM:** The `graph_paths` data already exists in the analysis table as human-readable strings. Parsing these into a structured node-edge format is straightforward. The complexity is in the frontend: building or integrating a graph visualization component (e.g., react-force-graph, vis.js, or D3) that renders an interactive mini-graph. The backend needs zero changes.

---

## Priority Matrix

| Priority | Feature | Difficulty | Impact |
|---|---|---|---|
| **P0** | 2. Resume Preview | EASY | Essential UX — recruiters need to see the original document |
| **P0** | 1. Email Notifications | MEDIUM | Core workflow — recruiters need to communicate decisions |
| **P1** | 4. Candidate Comparison | EASY | High recruiter value — comparing shortlisted candidates is a daily task |
| **P1** | 5. Job-to-Candidate Recs | EASY | Reduces time-to-fill by surfacing existing talent |
| **P1** | 8. Resume Improvement Suggestions | MEDIUM | Differentiator — most ATS tools don't give candidates feedback |
| **P2** | 6. Skill Gap Reports | EASY | Helps recruiters refine job postings |
| **P2** | 11. Multi-Job Routing | EASY | Increases candidate utilization across open roles |
| **P2** | 9. Batch Re-scoring | MEDIUM | Saves time when requirements evolve mid-search |
| **P2** | 13. Explainable Drilldown | MEDIUM | Builds trust in the AI scoring system |
| **P3** | 7. Similar Candidates | EASY | Nice-to-have for talent pooling |
| **P3** | 10. Calibration Dashboard | MEDIUM | Long-term trust metric — needs outcome data over time |
| **P3** | 12. Skill Trends | MEDIUM | Strategic insight — useful at scale |
| **P3** | 3. Social Profile Enrichment | HARD | High value but high cost/complexity/privacy risk |
