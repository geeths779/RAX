# RAX — Frontend Navigation Flow

## Route Map

```
/                          → LandingPage         (public)
/login                     → LoginPage           (public)
/register                  → RegisterPage        (public)
/app                       → ProtectedRoute → AppShell (requires JWT)
  /app/dashboard           → DashboardPage
  /app/jobs                → JobListPage
  /app/jobs/new            → CreateJobPage
  /app/jobs/:id            → JobDetailPage
  /app/upload/:jobId       → UploadPage
  /app/candidates/:jobId   → CandidateListPage
  /app/candidates/:jobId/:resumeId → CandidateDetailPage
  /app/feedback/:id        → FeedbackPage
/*                         → Redirect to /
```

---

## Authentication Flow

```
┌──────────────┐
│  App Mounts  │
│  hydrate()   │──── reads localStorage("rax_token","rax_user")
└──────┬───────┘     if found → isAuthenticated = true
       │             if not   → isAuthenticated = false
       ▼
┌──────────────┐     not authenticated     ┌──────────────┐
│ Visit /app/* │ ────────────────────────►  │  /login      │
│ ProtectedRoute│                           │  LoginPage   │
└──────┬───────┘                            └──────┬───────┘
       │ authenticated                             │
       ▼                                           │ POST /api/auth/login
┌──────────────┐                            ┌──────▼───────┐
│   AppShell   │◄───────────────────────────│ Store token  │
│   (sidebar   │    navigate('/app/dashboard')│ in Zustand  │
│    + outlet) │                            │ + localStorage│
└──────────────┘                            └──────────────┘
```

### Token Handling
- **Login**: Calls `POST /api/auth/login` → receives `{ access_token, token_type }` → decodes JWT payload client-side via `atob(token.split('.')[1])` to extract `sub` (user ID), `role` → stores token + user object in Zustand + `localStorage` as `rax_token` and `rax_user`.
- **Register**: Calls `POST /api/auth/register` → then auto-calls login with the same credentials.
- **Logout**: Clears Zustand store + removes `rax_token` and `rax_user` from `localStorage` → navigates to `/login`.
- **401 Interceptor**: Axios response interceptor catches any `401` → auto-calls `logout()` → redirects to `/login`.

---

## Page-by-Page Navigation

### 1. Landing Page (`/`)
- **Purpose**: Marketing page for unauthenticated visitors.
- **Navigation links**:
  - "Get Started" / "Sign Up" → `/register`
  - "Sign In" → `/login`
- **Components**: Hero, Features, HowItWorks, ScoringBreakdown, Comparison, FAQ, CTABanner, Footer.

### 2. Login Page (`/login`)
- **Purpose**: Email + password sign-in form.
- **On success**: → `/app/dashboard`
- **Links**: "Register" → `/register`

### 3. Register Page (`/register`)
- **Purpose**: Create account form (full name, email, password, role selector).
- **On success**: auto-login → `/app/dashboard`
- **Links**: "Sign In" → `/login`

### 4. Dashboard (`/app/dashboard`)
- **Purpose**: Overview stats — active job count, total job count, last 5 jobs.
- **Navigation links**:
  - "New Job" button → `/app/jobs/new`
  - Each recent job row → `/app/jobs/:id`
  - "Create your first job" → `/app/jobs/new` (if no jobs)

### 5. Job List (`/app/jobs`)
- **Purpose**: Table of all user's jobs with title, status badge, date, actions.
- **Navigation links**:
  - "Create Job" button → `/app/jobs/new`
  - Job title → `/app/jobs/:id`
  - "Upload" action → `/app/upload/:jobId`
  - "Candidates" action → `/app/candidates/:jobId`

### 6. Create Job (`/app/jobs/new`)
- **Purpose**: Form to create a new job (title, description, requirements).
- **On success**: → `/app/jobs/:newJobId`
- **Cancel button**: → `/app/jobs`

### 7. Job Detail (`/app/jobs/:id`)
- **Purpose**: Read-only display of job title, description, requirements JSON, status.
- **Navigation links**:
  - "Upload Resumes" button → `/app/upload/:id`
  - "View Candidates" button → `/app/candidates/:id`

### 8. Upload Page (`/app/upload/:jobId`)
- **Purpose**: Drag-and-drop file upload + real-time pipeline progress via WebSocket.
- **Flow**:
  1. User drops PDF/DOCX files → file list shown
  2. Click "Upload" → calls `POST /api/resumes/upload` per file
  3. WebSocket connects to `ws://host/ws/pipeline/:jobId?token=xxx`
  4. ProcessingCard components show stage-by-stage progress bars
  5. When all complete → "View Candidates" button appears
- **Navigation links**:
  - "View Candidates" → `/app/candidates/:jobId`

### 9. Candidate List (`/app/candidates/:jobId`)
- **Purpose**: Ranked table of candidates for a job, with scores and filter controls.
- **Features**: Sortable columns (overall/skills/exp/edu), min-score slider filter.
- **Navigation links**:
  - "Detail" per row → `/app/candidates/:jobId/:resumeId`

### 10. Candidate Detail (`/app/candidates/:jobId/:resumeId`)
- **Purpose**: Full analysis view — radar chart, score cards, strengths/gaps, AI explanation.
- **Navigation links**:
  - "Generate Feedback" button → calls API → navigates to `/app/feedback/:feedbackId`

### 11. Feedback Page (`/app/feedback/:id`)
- **Purpose**: Displays generated feedback text with "Copy to Clipboard" button.
- **No outbound navigation** (user uses sidebar to navigate elsewhere).

---

## Sidebar Navigation (AppShell)

The AppShell sidebar is visible on all `/app/*` routes:

```
┌─────────────────────┐
│  [R]  RAX           │
├─────────────────────┤
│  📊 Dashboard       │  → /app/dashboard
│  💼 Jobs            │  → /app/jobs
├─────────────────────┤
│  user@email.com     │
│  🚪 Logout          │  → clears auth → /login
└─────────────────────┘
```

- Mobile: sidebar hidden by default, toggled via hamburger menu icon.
- Active nav item highlighted with indigo background.

---

## User Journey (Happy Path)

```
Landing → Register → Dashboard → Create Job → Job Detail
                                                    │
                                              Upload Resumes
                                                    │
                                          (real-time processing)
                                                    │
                                            Candidate List
                                                    │
                                           Candidate Detail
                                                    │
                                          Generate Feedback
                                                    │
                                            Feedback Page
```

---

## WebSocket Flow (Upload Page)

```
Browser                          Server
  │                                │
  │─── POST /api/resumes/upload ──►│  (per file)
  │◄── { id, pipeline_status } ────│
  │                                │
  │─── WS /ws/pipeline/:jobId ───►│  (connect)
  │◄── "accepted" ─────────────────│
  │                                │
  │    (background pipeline runs)  │
  │◄── { stage:"parsing",         │
  │      status:"in_progress" } ───│
  │◄── { stage:"parsing",         │
  │      status:"complete" } ──────│
  │◄── { stage:"filtering", ... } │
  │     ... (6 more stages) ...    │
  │◄── { stage:"completed",       │
  │      status:"complete" } ──────│
  │                                │
  │─── "ping" ────────────────────►│
  │◄── "pong" ─────────────────────│
```

Each WS message has the shape:
```json
{
  "resume_id": "uuid",
  "stage": "parsing | filtering | graph_ingestion | embedding | hybrid_matching | scoring | completed",
  "status": "in_progress | complete | failed",
  "timestamp": "2026-04-11T10:30:00Z"
}
```
