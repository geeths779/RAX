# RAX — API Reference (Input / Output)

> Base URL: `http://localhost:8000`  
> Auth: All endpoints except Register, Login, and Health require `Authorization: Bearer <jwt>` header.

---

## Table of Contents

1. [Health Check](#1-health-check)
2. [Auth — Register](#2-auth--register)
3. [Auth — Login](#3-auth--login)
4. [Jobs — List](#4-jobs--list)
5. [Jobs — Create](#5-jobs--create)
6. [Jobs — Get by ID](#6-jobs--get-by-id)
7. [Jobs — Update](#7-jobs--update)
8. [Resumes — Upload](#8-resumes--upload)
9. [Resumes — Get Status](#9-resumes--get-status)
10. [Candidates — List for Job](#10-candidates--list-for-job)
11. [Analysis — Get for Resume](#11-analysis--get-for-resume)
12. [Feedback — Generate](#12-feedback--generate)
13. [Feedback — Get by ID](#13-feedback--get-by-id)
14. [WebSocket — Pipeline Status](#14-websocket--pipeline-status)

---

## 1. Health Check

```
GET /health
```

**Auth**: None

**Response** `200 OK`:
```json
{
  "status": "ok"
}
```

---

## 2. Auth — Register

```
POST /api/auth/register
```

**Auth**: None

**Request Body** (JSON):
```json
{
  "email": "user@example.com",
  "password": "securepass123",
  "full_name": "John Doe",
  "role": "recruiter"
}
```

| Field       | Type   | Required | Constraints                       |
|-------------|--------|----------|-----------------------------------|
| `email`     | string | Yes      | Valid email format                |
| `password`  | string | Yes      | Minimum 8 characters              |
| `full_name` | string | Yes      | 1–255 characters                  |
| `role`      | string | No       | `"recruiter"` (default) or `"hiring_manager"` |

**Response** `201 Created`:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "recruiter",
  "created_at": "2026-04-11T10:30:00.000Z"
}
```

**Error Responses**:
| Status | Detail                     |
|--------|----------------------------|
| `400`  | `"Email already registered"` |
| `400`  | `"Invalid role"`           |
| `422`  | Validation error (pydantic)|

---

## 3. Auth — Login

```
POST /api/auth/login
```

**Auth**: None

**Request Body** (JSON):
```json
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

| Field      | Type   | Required |
|------------|--------|----------|
| `email`    | string | Yes      |
| `password` | string | Yes      |

**Response** `200 OK`:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**JWT Payload**:
```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "role": "recruiter",
  "exp": 1712836200
}
```

**Error Responses**:
| Status | Detail                |
|--------|-----------------------|
| `401`  | `"Invalid credentials"` |

---

## 4. Jobs — List

```
GET /api/jobs
```

**Auth**: Bearer token required

**Response** `200 OK`:
```json
{
  "jobs": [
    {
      "id": "a1b2c3d4-...",
      "title": "Senior Python Developer",
      "description": "We are looking for...",
      "requirements_raw": {
        "skills": ["Python", "FastAPI", "PostgreSQL"]
      },
      "embedding_id": "qdrant-point-uuid-or-null",
      "created_by": "550e8400-...",
      "status": "active",
      "created_at": "2026-04-11T09:00:00.000Z"
    }
  ],
  "total": 1
}
```

Returns only jobs created by the authenticated user, ordered by `created_at` descending.

---

## 5. Jobs — Create

```
POST /api/jobs
```

**Auth**: Bearer token required (role: `recruiter` or `hiring_manager`)

**Request Body** (JSON):
```json
{
  "title": "Senior Python Developer",
  "description": "We are looking for an experienced Python developer...",
  "requirements_raw": {
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "experience_years": 5,
    "education": "Bachelor's in Computer Science"
  }
}
```

| Field              | Type   | Required | Constraints                  |
|--------------------|--------|----------|------------------------------|
| `title`            | string | Yes      | 1–255 characters             |
| `description`      | string | Yes      | Non-empty                    |
| `requirements_raw` | object | No       | Arbitrary JSON (skills, etc.)|

**Response** `201 Created`:
```json
{
  "id": "a1b2c3d4-...",
  "title": "Senior Python Developer",
  "description": "We are looking for...",
  "requirements_raw": { "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"] },
  "embedding_id": "qdrant-uuid-or-null",
  "created_by": "550e8400-...",
  "status": "active",
  "created_at": "2026-04-11T10:00:00.000Z"
}
```

**Side effects** (non-blocking, best-effort):
1. `GraphIngestionAgent` creates a Job node in Neo4j with skill relationships.
2. `EmbeddingAgent` generates a vector embedding and stores in Qdrant.

**Error Responses**:
| Status | Detail                    |
|--------|---------------------------|
| `401`  | Invalid/missing token     |
| `403`  | Insufficient permissions  |

---

## 6. Jobs — Get by ID

```
GET /api/jobs/{job_id}
```

**Auth**: Bearer token required

**Path Parameters**:
| Param    | Type | Description  |
|----------|------|--------------|
| `job_id` | UUID | The job's ID |

**Response** `200 OK`:
```json
{
  "id": "a1b2c3d4-...",
  "title": "Senior Python Developer",
  "description": "We are looking for...",
  "requirements_raw": { ... },
  "embedding_id": "...",
  "created_by": "550e8400-...",
  "status": "active",
  "created_at": "2026-04-11T10:00:00.000Z"
}
```

**Error Responses**:
| Status | Detail            |
|--------|-------------------|
| `404`  | `"Job not found"` |

---

## 7. Jobs — Update

```
PUT /api/jobs/{job_id}
```

**Auth**: Bearer token required (must be job owner)

**Path Parameters**:
| Param    | Type | Description  |
|----------|------|--------------|
| `job_id` | UUID | The job's ID |

**Request Body** (JSON, all fields optional):
```json
{
  "title": "Updated Title",
  "description": "Updated description...",
  "requirements_raw": { "skills": ["React", "TypeScript"] },
  "status": "closed"
}
```

| Field              | Type   | Required | Constraints                      |
|--------------------|--------|----------|----------------------------------|
| `title`            | string | No       | 1–255 characters if provided     |
| `description`      | string | No       | Non-empty if provided            |
| `requirements_raw` | object | No       | Arbitrary JSON                   |
| `status`           | string | No       | `"draft"`, `"active"`, `"closed"` |

**Response** `200 OK`: Updated `JobResponse` (same shape as Get).

**Error Responses**:
| Status | Detail                  |
|--------|-------------------------|
| `403`  | `"Not the job owner"`   |
| `404`  | `"Job not found"`       |

---

## 8. Resumes — Upload

```
POST /api/resumes/upload?job_id={uuid}
```

**Auth**: Bearer token required

**Query Parameters**:
| Param             | Type   | Required | Description                     |
|-------------------|--------|----------|---------------------------------|
| `job_id`          | UUID   | Yes      | Job to associate the resume with|
| `candidate_email` | string | No       | Candidate's email               |
| `candidate_name`  | string | No       | Candidate's name                |

**Request Body**: `multipart/form-data`
| Field  | Type | Required | Constraints             |
|--------|------|----------|-------------------------|
| `file` | File | Yes      | `.pdf` or `.docx` only  |

**Response** `201 Created`:
```json
{
  "id": "resume-uuid-...",
  "candidate_id": "candidate-uuid-...",
  "job_id": "a1b2c3d4-...",
  "file_path": "resumes/candidate-uuid/filename.pdf",
  "pipeline_status": "uploaded",
  "created_at": "2026-04-11T10:15:00.000Z"
}
```

**Side effects**:
1. File uploaded to Supabase Storage (best-effort).
2. If no existing candidate with the given email, a new Candidate is created.
3. **Background task** starts the AI pipeline (`PipelineOrchestrator.run()`).
4. Real-time status updates broadcast via WebSocket `/ws/pipeline/:jobId`.

**Error Responses**:
| Status | Detail                                           |
|--------|--------------------------------------------------|
| `400`  | `"Invalid file type. Allowed: .pdf, .docx"`      |
| `404`  | `"Job not found"`                                |

---

## 9. Resumes — Get Status

```
GET /api/resumes/{resume_id}/status
```

**Auth**: Bearer token required

**Path Parameters**:
| Param       | Type | Description     |
|-------------|------|-----------------|
| `resume_id` | UUID | The resume's ID |

**Response** `200 OK`:
```json
{
  "id": "resume-uuid-...",
  "pipeline_status": "completed",
  "created_at": "2026-04-11T10:15:00.000Z"
}
```

`pipeline_status` values: `"uploaded"`, `"processing"`, `"completed"`, `"failed"`

**Error Responses**:
| Status | Detail               |
|--------|----------------------|
| `404`  | `"Resume not found"` |

---

## 10. Candidates — List for Job

```
GET /api/jobs/{job_id}/candidates?min_score=50
```

**Auth**: Bearer token required

**Path Parameters**:
| Param    | Type | Description  |
|----------|------|--------------|
| `job_id` | UUID | The job's ID |

**Query Parameters**:
| Param       | Type  | Required | Description                          |
|-------------|-------|----------|--------------------------------------|
| `min_score` | float | No       | Filter: minimum overall score (0–100)|

**Response** `200 OK`:
```json
{
  "candidates": [
    {
      "id": "candidate-uuid-...",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": null,
      "overall_score": 85.5,
      "pipeline_status": "completed",
      "created_at": "2026-04-11T10:15:00.000Z"
    }
  ],
  "total": 1
}
```

- Only includes candidates whose resume has `pipeline_status = completed`.
- Sorted by `overall_score` descending (nulls last).

---

## 11. Analysis — Get for Resume

```
GET /api/resumes/{resume_id}/analysis
```

**Auth**: Bearer token required

**Path Parameters**:
| Param       | Type | Description     |
|-------------|------|-----------------|
| `resume_id` | UUID | The resume's ID |

**Response** `200 OK`:
```json
{
  "id": "analysis-uuid-...",
  "resume_id": "resume-uuid-...",
  "job_id": "job-uuid-...",
  "overall_score": 85.5,
  "skills_score": 90.0,
  "experience_score": 80.0,
  "education_score": 75.0,
  "semantic_similarity": 0.87,
  "structural_match": 0.91,
  "explanation": "The candidate demonstrates strong backend skills with 5+ years of Python experience...",
  "strengths": [
    "Strong Python and FastAPI expertise",
    "Relevant PostgreSQL experience",
    "Docker containerization skills"
  ],
  "gaps": [
    "No Kubernetes experience mentioned",
    "Limited frontend skills"
  ],
  "graph_paths": [
    "Resume→HAS_SKILL→Python←REQUIRES_SKILL←Job",
    "Resume→HAS_SKILL→FastAPI←REQUIRES_SKILL←Job"
  ],
  "created_at": "2026-04-11T10:20:00.000Z"
}
```

**Error Responses**:
| Status | Detail                                              |
|--------|-----------------------------------------------------|
| `404`  | `"Analysis not found — pipeline may not be complete"` |

---

## 12. Feedback — Generate

```
POST /api/feedback/{candidate_id}/{job_id}
```

**Auth**: Bearer token required (role: `recruiter` only)

**Path Parameters**:
| Param          | Type | Description      |
|----------------|------|------------------|
| `candidate_id` | UUID | The candidate's ID |
| `job_id`       | UUID | The job's ID     |

**Request Body**: None

**Response** `201 Created`:
```json
{
  "id": "feedback-uuid-...",
  "candidate_id": "candidate-uuid-...",
  "job_id": "job-uuid-...",
  "resume_id": "resume-uuid-...",
  "content": "Dear Candidate,\n\nThank you for applying for the Senior Python Developer position. Based on our analysis...\n\nStrengths:\n- Strong Python expertise...\n\nAreas for improvement:\n- Consider gaining Kubernetes experience...\n\nBest regards,\nRAX Hiring Team",
  "sent_at": null,
  "created_at": "2026-04-11T10:25:00.000Z"
}
```

**Side effects**:
- `FeedbackAgent` is invoked to generate personalized feedback using Gemini LLM.
- If the agent fails, a fallback string `"Automated feedback generation pending."` is stored.

**Error Responses**:
| Status | Detail                                            |
|--------|---------------------------------------------------|
| `403`  | `"Insufficient permissions"` (non-recruiter)      |
| `404`  | `"Resume not found for this candidate/job"`        |
| `404`  | `"Analysis not found — pipeline not complete"`      |

---

## 13. Feedback — Get by ID

```
GET /api/feedback/{feedback_id}
```

**Auth**: Bearer token required

**Path Parameters**:
| Param         | Type | Description       |
|---------------|------|-------------------|
| `feedback_id` | UUID | The feedback's ID |

**Response** `200 OK`:
```json
{
  "id": "feedback-uuid-...",
  "candidate_id": "candidate-uuid-...",
  "job_id": "job-uuid-...",
  "resume_id": "resume-uuid-...",
  "content": "Dear Candidate,\n\n...",
  "sent_at": null,
  "created_at": "2026-04-11T10:25:00.000Z"
}
```

**Error Responses**:
| Status | Detail                 |
|--------|------------------------|
| `404`  | `"Feedback not found"` |

---

## 14. WebSocket — Pipeline Status

```
WS /ws/pipeline/{job_id}?token={jwt}
```

**Auth**: Optional JWT via query parameter `token`. In dev mode, unauthenticated connections are allowed.

**Path Parameters**:
| Param    | Type   | Description  |
|----------|--------|--------------|
| `job_id` | string | The job's ID |

**Client → Server Messages**:
```
"ping"    → server responds with "pong"
```

**Server → Client Messages** (JSON):
```json
{
  "resume_id": "resume-uuid-...",
  "stage": "parsing",
  "status": "in_progress",
  "timestamp": "2026-04-11T10:15:01.000Z"
}
```

**Stage values** (in pipeline order):
| Stage              | Description                                    |
|--------------------|------------------------------------------------|
| `parsing`          | Extracting text and structured data from PDF   |
| `filtering`        | Removing PII / bias-sensitive information      |
| `graph_ingestion`  | Creating nodes/relationships in Neo4j          |
| `embedding`        | Generating and storing vector embedding        |
| `hybrid_matching`  | Computing graph + semantic fusion scores       |
| `scoring`          | AI-powered multi-dimensional scoring           |
| `completed`        | Pipeline finished successfully                 |

**Status values**:
| Status        | Description               |
|---------------|---------------------------|
| `in_progress` | Stage is currently running|
| `complete`    | Stage finished OK         |
| `failed`      | Stage encountered an error|

**Close Codes**:
| Code   | Reason           |
|--------|------------------|
| `4001` | `"Invalid token"` |

---

## Common Error Response Shape

All HTTP errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

For `422 Validation Error` (Pydantic):
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```
