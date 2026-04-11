# RAX — Final Implementation Plan (Person 2 + Person 3)

> **Created:** April 10, 2026  
> **Baseline:** Person 1 (Backend Core) is 100% complete — all DB, models, schemas, auth, routes, tests done.  
> **Goal:** Ship complete end-to-end RAX application.

---

## Timeline & Parallelization

```
  DAY 1           DAY 2           DAY 3           DAY 4           DAY 5
  ─────           ─────           ─────           ─────           ─────
  P2: Phase 5     P2: Phase 6     P2: Phase 7     P2: Phase 8     P2: E2E Test
  (Matching+      (Feedback+      (WebSocket)     (Integration)   + Bug Fixes
   Scoring)        Smoke Test)

  P3: Phase 1     P3: Phase 2     P3: Phase 3+4   P3: Phase 5+6   P3: Phase 7+8
  (Setup)         (Auth)          (Shell+Dash)    (Jobs+Upload)   (Candidates+
                                                                   Feedback)
                                                   DAY 6
                                                   ─────
                                                   P3: Phase 9+10
                                                   (Polish+Deploy)
```

**Key sync point:** Person 3 Phase 6 (WebSocket UI) needs Person 2 Phase 7 (WebSocket endpoint) — target Day 4.

---

## PERSON 2 — AI Pipeline (Phases 5–8)

> **Scope:** `backend/app/agents/` + `backend/app/api/routes/ws.py`  
> **DO NOT TOUCH:** `backend/app/api/routes/{auth,jobs,resumes,candidates,analysis,feedback}.py`, `frontend/`

---

### P2-Phase 5: HybridMatchingAgent + ScoringAgent (Full Implementation)

**Goal:** Replace hardcoded zeros in `HybridMatchingAgent.run()` with real Neo4j + Qdrant queries. Verify `ScoringAgent` consumes real match data.

**Prerequisites:**
- Docker services running: `docker-compose up -d` (Neo4j + Qdrant)
- `GOOGLE_API_KEY` set in `.env`
- Phase 3 + 4 test data loaded (run `test_phase3.py` + `test_phase4.py`)

#### Tasks

**5.1 — Inject clients into HybridMatchingAgent** (`orchestrator.py`)
- Pass `neo4j_driver` and `qdrant_client` to `HybridMatchingAgent` constructor
- Update `HybridMatchingAgent.__init__()` to accept and store both

**5.2 — Implement structural score** (`hybrid_matching_agent.py`)
- Execute `DIRECT_SKILL_MATCH` Cypher via `self._driver.session()` → `session.run()`
- Execute `SIMILAR_SKILL_MATCH` Cypher
- Compute: `structural_score = (direct_count + 0.5 * similar_count) / total_required_skills`
- Cap at 1.0

**5.3 — Implement semantic score** (`hybrid_matching_agent.py`)
- Retrieve resume vector from Qdrant `resumes` collection by `ctx.resume_id`
- Search `job_descriptions` collection with that vector, filter by `ctx.job_id`
- `semantic_score` = top hit's cosine similarity (0.0–1.0)

**5.4 — Implement experience score** (`hybrid_matching_agent.py`)
- From `DIRECT_SKILL_MATCH` results: compare `candidate_years` vs `required_years`
- `experience_score = avg(min(candidate_years / required_years, 1.0))` across matched skills
- Default to 0.5 if no year data available

**5.5 — Implement education score** (`hybrid_matching_agent.py`)
- Execute `EDUCATION_MATCH` Cypher
- Map levels using `DEGREE_LEVELS` dict
- `education_score = min(candidate_level / required_level, 1.0)`
- Default to 0.5 if no education data

**5.6 — Implement hybrid fusion** (`hybrid_matching_agent.py`)
- `hybrid_score = 0.50 * structural + 0.30 * semantic + 0.15 * experience + 0.05 * education`
- Populate `ctx.match_result` with all sub-scores + `matched_skills`, `similar_skills`, `skill_gaps`, `graph_paths`

**5.7 — Verify ScoringAgent** (`scoring_agent.py`)
- Confirm it correctly builds prompt from real `ctx.match_result`
- Confirm JSON parsing handles Gemini's response (with or without markdown fences)
- No code changes expected if match_result shape is correct

#### Files Modified
- `backend/app/agents/hybrid_matching_agent.py` (main work)
- `backend/app/agents/orchestrator.py` (pass clients to HybridMatchingAgent)

#### Verify
```bash
cd backend
python test_phase3.py   # ensure Neo4j test data exists
python test_phase4.py   # ensure Qdrant test data exists
# Then run a test matching the test candidate against test job
python -c "
import asyncio
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from app.agents.hybrid_matching_agent import HybridMatchingAgent
from app.agents.pipeline_context import PipelineContext

async def test():
    driver = AsyncGraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'rax_dev_password'))
    qdrant = QdrantClient(url='http://localhost:6333')
    agent = HybridMatchingAgent(neo4j_driver=driver, qdrant_client=qdrant)
    ctx = PipelineContext(resume_id='test-embed-1', job_id='test-job-1')
    ctx.graph_node_id = 'test-candidate-1'
    ctx.qdrant_point_id = 'test-embed-1'
    ctx = await agent.run(ctx)
    print(f'Hybrid score: {ctx.match_result[\"hybrid_score\"]}')
    assert ctx.match_result['hybrid_score'] > 0, 'Score should be > 0'
    assert all(0 <= ctx.match_result[k] <= 1.0 for k in ['structural_score','semantic_score','experience_score','education_score'])
    print('✅ All sub-scores in valid range')
    await driver.close()
asyncio.run(test())
"
```

---

### P2-Phase 6: FeedbackAgent Finish + Full Pipeline Smoke Test

**Goal:** Ensure feedback generation works end-to-end. Run the complete pipeline from raw text to analysis output.

**Prerequisites:** Phase 5 complete

#### Tasks

**6.1 — Verify FeedbackAgent** (`feedback_agent.py`)
- Current code already calls Gemini with `FEEDBACK_PROMPT` and stores in `ctx.analysis["feedback"]` — this works.
- The `POST /feedback` route in Person 1's code already handles persistence (creates `Feedback` record in DB).
- **No code changes needed unless** the `match_result` is empty when called from the route (check that the route populates `ctx.match_result` — currently it doesn't).

**6.2 — Fix feedback route integration** (coordinate with Person 1 if needed)
- The `POST /feedback` route creates a `PipelineContext` but only populates `ctx.analysis` (from the Analysis DB record), NOT `ctx.match_result`.
- Option A: Store `match_result` in the Analysis model's `graph_paths` JSONB field during scoring → retrieve in feedback route.
- Option B: Make `FeedbackAgent` work with just `ctx.analysis` (it already does — it reads `explanation`, `matched_skills` comes from `match_result` which will be empty).
- **Recommended:** Update `ScoringAgent.run()` to also store `matched_skills`, `skill_gaps`, `similar_skills` into `ctx.analysis` so `FeedbackAgent` can access them without needing `match_result`.

**6.3 — Full pipeline smoke test**
```bash
cd backend
python -c "
import asyncio
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from app.agents.orchestrator import PipelineOrchestrator

async def test():
    driver = AsyncGraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'rax_dev_password'))
    qdrant = QdrantClient(url='http://localhost:6333')
    orch = PipelineOrchestrator(neo4j_driver=driver, qdrant_client=qdrant)
    ctx = await orch.run(
        resume_id='smoke-test-1',
        job_id='test-job-1',
        raw_text='John Doe. Python developer with 5 years experience in FastAPI, PostgreSQL, Docker. BS Computer Science from MIT. Worked at Google and Meta.'
    )
    assert ctx.error is None, f'Pipeline failed: {ctx.error}'
    assert ctx.analysis.get('overall_score', 0) > 0, 'Score should be > 0'
    print(f'✅ Pipeline complete. Score: {ctx.analysis[\"overall_score\"]}/100')
    print(f'   Explanation: {ctx.analysis.get(\"explanation\", \"N/A\")}')
    await driver.close()
asyncio.run(test())
"
```

#### Files Modified
- `backend/app/agents/scoring_agent.py` (minor: copy match skills into analysis)
- `backend/app/agents/feedback_agent.py` (no changes expected)

---

### P2-Phase 7: WebSocket Real-Time Broadcasting

**Goal:** Create `/ws/pipeline/{job_id}` endpoint so Person 3's frontend can receive live stage updates.

**Prerequisites:** Phase 6 complete

#### Tasks

**7.1 — Create `ws.py`** (`backend/app/api/routes/ws.py`)

```python
# Implement:
# - ConnectionManager class (in-memory dict of job_id → set of WebSocket connections)
# - manager.connect(job_id, websocket) — accept + store
# - manager.disconnect(job_id, websocket) — remove
# - manager.broadcast(job_id, message: dict) — send JSON to all connections for that job
# - WS route: @router.websocket("/ws/pipeline/{job_id}")
# - Optional: validate JWT from query param ?token=xxx
# - make_ws_callback(manager, job_id) → StatusCallback function for orchestrator
```

**Message format (contract with Person 3):**
```json
{
    "resume_id": "uuid-string",
    "stage": "parsing|filtering|graph_ingestion|embedding|hybrid_matching|scoring|completed",
    "status": "in_progress|complete|failed",
    "timestamp": "2026-04-10T12:00:00Z"
}
```

**7.2 — Register WS router in `main.py`**
- Add: `from app.api.routes import ws`
- Add: `app.include_router(ws.router, tags=["WebSocket"])`

**7.3 — Update resume upload route** (`resumes.py`) 
- In `_run_pipeline()`, create a `ConnectionManager` instance (or use a global singleton) and pass `make_ws_callback(manager, job_id)` as `on_status_change` to `PipelineOrchestrator`

#### Files Created
- `backend/app/api/routes/ws.py` (NEW)

#### Files Modified
- `backend/app/main.py` (add WS router)
- `backend/app/api/routes/resumes.py` (wire callback into pipeline)

#### Verify
```bash
# Terminal 1: Start server
cd backend && uvicorn app.main:app --reload

# Terminal 2: Connect WebSocket client
pip install websockets
python -c "
import asyncio, websockets, json
async def listen():
    async with websockets.connect('ws://localhost:8000/ws/pipeline/test-job-1') as ws:
        print('Connected. Waiting for events...')
        async for msg in ws:
            print(json.loads(msg))
asyncio.run(listen())
"

# Terminal 3: Trigger pipeline via API
curl -X POST http://localhost:8000/api/resumes/upload ...
# → Terminal 2 should show stage events
```

---

### P2-Phase 8: Integration + DB Persistence

**Goal:** Wire everything into Person 1's existing routes. Add DB persistence for analysis results.

**Prerequisites:** Phase 7 complete, Person 1's routes available (they are)

#### Tasks

**8.1 — Add DB persistence to ScoringAgent** (`scoring_agent.py`)
- After Gemini scoring, persist to `analyses` table via SQLAlchemy
- Accept optional `db: AsyncSession` parameter
- Create `Analysis` record with: `resume_id`, `job_id`, `overall_score`, `skills_score`, `experience_score`, `education_score`, `explanation`, `strengths`, `gaps`, `graph_paths` (from match_result)

**8.2 — Update resume pipeline status** (`orchestrator.py`)
- Accept optional `db: AsyncSession`
- After each stage, update `Resume.pipeline_status` in DB
- On completion: set `pipeline_status = "completed"`
- On failure: set `pipeline_status = "failed"`

**8.3 — Wire real clients into `_run_pipeline`** (`resumes.py`)
- Import `get_neo4j_driver`, `get_qdrant_client`
- Pass them to `PipelineOrchestrator` constructor
- Pass DB session for persistence

**8.4 — Wire WebSocket into upload flow** (`resumes.py`)
- Import the global `ConnectionManager` singleton from `ws.py`
- Create callback via `make_ws_callback(manager, str(job_id))`
- Pass as `on_status_change` to `PipelineOrchestrator`

**8.5 — Add WebSocket JWT auth** (`ws.py`)
- On WS connect, read `?token=xxx` query param
- Validate JWT using same logic as `get_current_user`
- Reject connection if invalid

#### Files Modified
- `backend/app/agents/scoring_agent.py` (DB persistence)
- `backend/app/agents/orchestrator.py` (DB session, pipeline status updates)
- `backend/app/api/routes/resumes.py` (wire real clients + WS callback)
- `backend/app/api/routes/ws.py` (JWT auth)

#### Verify
```bash
# Full E2E test:
# 1. Register user → login → get JWT
# 2. Create job (POST /api/jobs) → triggers graph_ingestion + embedding
# 3. Upload resume (POST /api/resumes/upload) → triggers full pipeline
# 4. Poll GET /api/resumes/{id}/status until "completed"
# 5. GET /api/jobs/{job_id}/candidates → ranked list with scores
# 6. GET /api/resumes/{resume_id}/analysis → full scoring breakdown
# 7. POST /api/feedback/{candidate_id}/{job_id} → generated feedback
```

---

## PERSON 3 — Frontend (Phases 1–10)

> **Scope:** `frontend/` (entire directory)  
> **DO NOT TOUCH:** `backend/`  
> **API Base:** `http://localhost:8000/api` (proxy via vite dev server)  
> **Strategy:** Build all UI with mock data first, swap to real API when backend is running.

---

### P3-Phase 1: Project Setup + Folder Structure + Dependencies

**Goal:** Install remaining deps, configure vite proxy, create folder structure.

**Prerequisites:** None

#### Tasks

**1.1 — Install additional dependencies**
```bash
cd frontend
npm install react-hook-form @hookform/resolvers zod react-dropzone
npm install -D @types/react-dropzone
```
> Note: `axios`, `zustand`, `recharts`, `react-router-dom`, `tailwindcss` already installed.

**1.2 — Add shadcn/ui components**
```bash
npx shadcn@latest init
npx shadcn@latest add button card input label table badge dialog select tabs toast separator avatar dropdown-menu sheet skeleton alert
```

**1.3 — Configure vite proxy** (`vite.config.ts`)
```typescript
server: {
    proxy: {
        '/api': { target: 'http://localhost:8000', changeOrigin: true },
        '/ws': { target: 'ws://localhost:8000', ws: true },
    },
},
```

**1.4 — Create folder structure**
```
frontend/src/
├── components/
│   ├── ui/               # shadcn/ui (auto-generated)
│   ├── landing/           # existing landing components
│   ├── layout/
│   │   ├── AppShell.tsx
│   │   └── ProtectedRoute.tsx
│   ├── ProcessingCard.tsx
│   ├── RadarChart.tsx
│   └── ScoreCard.tsx
├── pages/
│   ├── LandingPage.tsx    # existing
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── DashboardPage.tsx
│   ├── JobListPage.tsx
│   ├── CreateJobPage.tsx
│   ├── JobDetailPage.tsx
│   ├── UploadPage.tsx
│   ├── CandidateListPage.tsx
│   ├── CandidateDetailPage.tsx
│   └── FeedbackPage.tsx
├── services/
│   ├── api.ts             # Axios instance + interceptor
│   ├── authService.ts
│   ├── jobService.ts
│   ├── resumeService.ts
│   ├── candidateService.ts
│   └── feedbackService.ts
├── store/
│   └── authStore.ts       # Zustand
├── hooks/
│   └── useProcessingStream.ts  # WebSocket hook
├── types/
│   └── index.ts           # All TypeScript interfaces
└── lib/
    └── utils.ts           # existing (shadcn utility)
```

**1.5 — Create TypeScript types** (`src/types/index.ts`)
```typescript
// Match backend Pydantic schemas exactly:
export interface User { id: string; email: string; full_name: string; role: 'recruiter' | 'hiring_manager'; }
export interface TokenResponse { access_token: string; token_type: string; }
export interface Job { id: string; title: string; description: string; requirements_raw: Record<string, any>; status: string; created_at: string; }
export interface JobListResponse { jobs: Job[]; total: number; }
export interface ResumeUploadResponse { resume_id: string; candidate_id: string; status: string; }
export interface ResumeStatus { resume_id: string; pipeline_status: string; }
export interface Candidate { id: string; name: string | null; email: string | null; overall_score: number; skills_score: number; experience_score: number; education_score: number; explanation: string; }
export interface Analysis { overall_score: number; skills_score: number; experience_score: number; education_score: number; strengths: string[]; gaps: string[]; explanation: string; }
export interface Feedback { id: string; content: string; sent_at: string | null; created_at: string; }
```

#### Verify
```bash
npm run dev   # → app loads, landing page still works, no errors
```

---

### P3-Phase 2: Auth (Store + Service + Pages)

**Goal:** Login/register pages, JWT token management, protected route wrapper.

**Prerequisites:** Phase 1

#### Tasks

**2.1 — Create API client** (`src/services/api.ts`)
- Axios instance with `baseURL: '/api'`
- Request interceptor: attach `Authorization: Bearer <token>` from authStore
- Response interceptor: on 401, call `authStore.logout()` and redirect to `/login`

**2.2 — Create auth store** (`src/store/authStore.ts`)
- Zustand store with:
  - `token: string | null` (persisted to localStorage)
  - `user: User | null`
  - `isAuthenticated: boolean` (computed from token)
  - `login(email, password)` → call API → store token + decode user from JWT
  - `register(email, password, full_name, role)` → call API → auto-login
  - `logout()` → clear token + user

**2.3 — Create auth service** (`src/services/authService.ts`)
- `login(email, password): Promise<TokenResponse>`
- `register(email, password, full_name, role): Promise<User>`

**2.4 — Create LoginPage** (`src/pages/LoginPage.tsx`)
- react-hook-form + zod validation
- Email + password fields
- Submit → `authStore.login()` → redirect to `/dashboard`
- Link to register page

**2.5 — Create RegisterPage** (`src/pages/RegisterPage.tsx`)
- Email + password + full name + role selector (recruiter/hiring_manager)
- Submit → `authStore.register()` → redirect to `/dashboard`

**2.6 — Create ProtectedRoute** (`src/components/layout/ProtectedRoute.tsx`)
- Check `authStore.isAuthenticated`
- If not → redirect to `/login`
- If yes → render `<Outlet />`

#### Verify
- Register → login → redirected to `/dashboard` (blank page ok)
- Refresh page → still authenticated (token in localStorage)
- Logout → redirected to `/login`
- Access `/dashboard` without token → redirected to `/login`

---

### P3-Phase 3: App Shell + Routing

**Goal:** Sidebar layout, route structure, navigation.

**Prerequisites:** Phase 2

#### Tasks

**3.1 — Create AppShell** (`src/components/layout/AppShell.tsx`)
- Left sidebar with links: Dashboard, Jobs, Upload (collapsible on mobile)
- Top bar with user email + logout button
- Main content area renders child routes via `<Outlet />`
- Use shadcn Sheet for mobile sidebar

**3.2 — Update App.tsx routes**
```
/               → LandingPage (public)
/login          → LoginPage (public)
/register       → RegisterPage (public)
/app            → ProtectedRoute → AppShell
  /app/dashboard        → DashboardPage
  /app/jobs             → JobListPage
  /app/jobs/new         → CreateJobPage
  /app/jobs/:id         → JobDetailPage
  /app/upload/:jobId    → UploadPage
  /app/candidates/:jobId → CandidateListPage
  /app/candidates/:jobId/:resumeId → CandidateDetailPage
  /app/feedback/:id     → FeedbackPage
```

#### Verify
- Navigate between pages via sidebar
- URL changes reflect in sidebar active state
- Protected routes redirect to login when unauthenticated

---

### P3-Phase 4: Dashboard

**Goal:** Summary cards + recent jobs widget.

**Prerequisites:** Phase 3

#### Tasks

**4.1 — Create DashboardPage** (`src/pages/DashboardPage.tsx`)
- Stat cards: Active Jobs count, Total Resumes processed, Avg Score
- Fetch from `GET /api/jobs` → aggregate counts
- Recent jobs list (last 5)
- Quick action buttons: "Create Job", "View All Jobs"

**4.2 — Create dashboard service** (`src/services/jobService.ts`)
- `getJobs(): Promise<JobListResponse>` → `GET /api/jobs`

**Mock strategy:** If API unavailable, return hardcoded data:
```typescript
const MOCK_JOBS = [
    { id: '1', title: 'Senior Python Dev', status: 'active', created_at: '2026-04-10' },
    // ...
];
```

#### Verify
- Dashboard shows stat cards with counts
- Recent jobs list renders
- Click job → navigates to job detail

---

### P3-Phase 5: Job Management

**Goal:** Job CRUD pages.

**Prerequisites:** Phase 3

#### Tasks

**5.1 — Create jobService** (`src/services/jobService.ts`)
- `getJobs()` → `GET /api/jobs`
- `createJob(data)` → `POST /api/jobs`
- `getJob(id)` → `GET /api/jobs/{id}`

**5.2 — Create JobListPage** (`src/pages/JobListPage.tsx`)
- Data table with columns: Title, Status (badge), Created At, Actions
- Status badges: Active (green), Closed (gray), Draft (yellow)
- "Create Job" button → navigates to `/app/jobs/new`
- Click row → navigates to `/app/jobs/:id`

**5.3 — Create CreateJobPage** (`src/pages/CreateJobPage.tsx`)
- Form: Title (input), Description (textarea), Requirements (textarea — parsed as JSON or free text)
- react-hook-form + zod validation
- Submit → `createJob()` → redirect to `/app/jobs/:id`

**5.4 — Create JobDetailPage** (`src/pages/JobDetailPage.tsx`)
- Read-only display of job title, description, requirements
- Action buttons: "Upload Resumes" → `/app/upload/:jobId`, "View Candidates" → `/app/candidates/:jobId`
- Status badge

#### Verify
- Create job → appears in list → click to view detail
- "Upload Resumes" button navigates correctly
- "View Candidates" button navigates correctly

---

### P3-Phase 6: Resume Upload + WebSocket Live Processing

**Goal:** Drag-drop upload + real-time pipeline status.

**Prerequisites:** Phase 5. WebSocket UI needs Person 2 Phase 7 (can mock until then).

#### Tasks

**6.1 — Create resumeService** (`src/services/resumeService.ts`)
- `uploadResumes(files: File[], jobId: string)` → `POST /api/resumes/upload` (multipart FormData)
- `getResumeStatus(resumeId: string)` → `GET /api/resumes/{id}/status`

**6.2 — Create useProcessingStream hook** (`src/hooks/useProcessingStream.ts`)
```typescript
function useProcessingStream(jobId: string) {
    // Returns: { statuses: Map<resumeId, {stage, status, score?}>, isConnected, error }
    // Connects to: ws://localhost:8000/ws/pipeline/{jobId}?token=xxx
    // Parses JSON messages: { resume_id, stage, status, timestamp }
    // Auto-reconnect on disconnect (3 retries, exponential backoff)
}
```

**6.3 — Create ProcessingCard** (`src/components/ProcessingCard.tsx`)
- Per-resume card showing filename + pipeline stages
- Stages animate left-to-right:  parsing → filtering → graph → embed → match → score → ✅
- Each stage: gray (pending), blue pulse (in_progress), green (complete), red (failed)

**6.4 — Create UploadPage** (`src/pages/UploadPage.tsx`)
- `react-dropzone` zone: "Drop PDF/DOCX files here"
- File list with remove button
- "Upload" button → calls `uploadResumes()`
- After upload → connect WebSocket → show `ProcessingCard` per resume
- Show "View Candidates" button when all resumes complete

**Mock WebSocket (until Person 2 Phase 7 ready):**
```typescript
// In useProcessingStream, if VITE_MOCK_WS=true:
// Simulate stages with setTimeout every 2 seconds
```

#### Verify
- Drop files → shows file list
- Upload → processing cards appear with animated stages
- All complete → "View Candidates" link appears

---

### P3-Phase 7: Candidate Ranking

**Goal:** Ranked candidate table with filtering.

**Prerequisites:** Phase 6

#### Tasks

**7.1 — Create candidateService** (`src/services/candidateService.ts`)
- `getCandidates(jobId, sortBy?, order?)` → `GET /api/jobs/{jobId}/candidates`
- `getAnalysis(resumeId)` → `GET /api/resumes/{resumeId}/analysis`

**7.2 — Create CandidateListPage** (`src/pages/CandidateListPage.tsx`)
- Table columns: Rank, Name (anonymized by default), Overall Score, Skills, Experience, Education, Status, Actions
- All score columns sortable
- Minimum score slider filter
- "Reveal Identity" toggle per candidate (shows real name)
- Click "View Detail" → `/app/candidates/:jobId/:resumeId`

#### Verify
- Candidates sorted by overall_score descending
- Sort by different columns works
- Score slider filters candidates
- Click detail → navigates to detail page

---

### P3-Phase 8: Candidate Detail + Analysis + Feedback

**Goal:** Full scoring breakdown with radar chart + feedback generation.

**Prerequisites:** Phase 7

#### Tasks

**8.1 — Create RadarChart** (`src/components/RadarChart.tsx`)
- Recharts `RadarChart` with axes: Skills, Experience, Education
- Scores normalized to 0–100

**8.2 — Create ScoreCard** (`src/components/ScoreCard.tsx`)
- Green card for strengths, red card for gaps
- Icon + text

**8.3 — Create CandidateDetailPage** (`src/pages/CandidateDetailPage.tsx`)
- Header: candidate ID, overall score badge
- Radar chart (skills / experience / education scores)
- Strengths section (green ScoreCards)
- Gaps section (red ScoreCards)
- AI Explanation text block
- "Generate Feedback" button → `POST /api/feedback/{candidateId}/{jobId}`
- After generation → navigate to feedback page

**8.4 — Create feedbackService** (`src/services/feedbackService.ts`)
- `generateFeedback(candidateId, jobId)` → `POST /api/feedback/{candidateId}/{jobId}`
- `getFeedback(feedbackId)` → `GET /api/feedback/{id}`

**8.5 — Create FeedbackPage** (`src/pages/FeedbackPage.tsx`)
- Display generated feedback text (150–200 words)
- "Copy to Clipboard" button
- "Back to Candidates" button

#### Verify
- Radar chart renders with correct scores
- Strengths/gaps cards display
- Generate feedback → view feedback text
- Copy to clipboard works

---

### P3-Phase 9: Polish + Error Handling

**Goal:** Loading states, error boundaries, responsive design.

**Prerequisites:** Phases 4–8

#### Tasks

**9.1 — Add loading skeletons** (all pages)
- Use shadcn `Skeleton` component during API fetches

**9.2 — Add error handling**
- Global error toast (shadcn Toast) for API failures
- Empty state UI for no jobs, no candidates, etc.

**9.3 — Responsive design**
- Mobile sidebar (Sheet)
- Tables → card layout on mobile
- Upload zone touch-friendly

**9.4 — Remove all `any` types** (`types/index.ts`)
- Ensure all API responses typed
- No TypeScript errors

#### Verify
- `npm run build` → zero errors
- All pages render on mobile viewport
- API errors show toast, not blank screen

---

### P3-Phase 10: Deployment Config

**Goal:** Production-ready build + Vercel deployment.

**Prerequisites:** Phase 9

#### Tasks

**10.1 — Create vercel.json**
```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```

**10.2 — Environment variables**
- `VITE_API_URL` → production backend URL
- Remove mock flags

**10.3 — Build and test**
```bash
npm run build
npm run preview
```

---

## Cross-Dependency Matrix

| Person 3 Needs From Person 2 | When | Status |
|-------------------------------|------|--------|
| WebSocket endpoint `WS /ws/pipeline/{job_id}` | P3 Phase 6 | Person 2 Phase 7 |
| Stage message format: `{resume_id, stage, status, timestamp}` | P3 Phase 6 | Defined in contract |

| Person 2 Needs From Person 3 | When | Status |
|-------------------------------|------|--------|
| Nothing — Person 2 is independent of frontend | — | ✅ |

| Both Need | When | How |
|-----------|------|-----|
| Docker services (Neo4j + Qdrant) | Person 2 all phases | `docker-compose up -d` |
| Backend running (`uvicorn`) | Person 3 all phases (or mock) | `cd backend && uvicorn app.main:app --reload` |
| `.env` configured | Before any work | Copy `.env.example` → fill values |

---

## Quick-Start Commands

```bash
# Person 2 — start working
docker-compose up -d
cd backend
pip install -r requirements.txt
# Set GOOGLE_API_KEY in .env
python test_phase3.py    # verify Neo4j data
python test_phase4.py    # verify Qdrant data
# → Start Phase 5 implementation

# Person 3 — start working
cd frontend
npm install
npm install react-hook-form @hookform/resolvers zod react-dropzone
npx shadcn@latest init
npm run dev
# → Start Phase 1 folder structure
```
