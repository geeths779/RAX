# RAX — Person 2 AI Pipeline: Phase-by-Phase Implementation Plan

> **Owner:** Person 2 — AI Pipeline (Gemini, Neo4j, Qdrant, WebSocket)  
> **Created:** April 5, 2026  
> **Scope:** `backend/app/agents/`, `backend/app/api/routes/ws.py`  
> **Rule:** One phase at a time. Stop after each phase. Verify everything works. Then proceed.

---

## Dependency Report for Other Developers

> **Person 1 (Backend Core)** and **Person 3 (Frontend)** — please read this section.  
> This lists exactly what we need from you and when, so you can plan your work in parallel.

### What Person 2 needs FROM Person 1 (Backend Core)

| Needed By | What | Details | Status |
|-----------|------|---------|--------|
| Phase 8 | `backend/app/db/session.py` | `get_db` async dependency returning SQLAlchemy `AsyncSession` | ❌ Pending |
| Phase 8 | `backend/app/db/neo4j_client.py` | `get_neo4j_session()` async context manager | ❌ Pending |
| Phase 8 | `backend/app/db/qdrant_client.py` | `get_qdrant_client()` singleton | ❌ Pending |
| Phase 8 | `backend/app/models/` | SQLAlchemy models for `resume`, `analysis`, `feedback` tables | ❌ Pending |
| Phase 8 | `POST /resumes` route | Route that calls `PipelineOrchestrator.run()` as `BackgroundTask` | ❌ Pending |
| Phase 8 | `POST /jobs` route | Route that calls `EmbeddingAgent.embed_job()` + `GraphIngestionAgent.ingest_job()` | ❌ Pending |
| Phase 8 | `POST /feedback` route | Route that calls `FeedbackAgent.run()` on demand | ❌ Pending |

**Key:** Nothing from Person 1 is needed until Phase 8. Phases 2–7 are fully self-contained.

### What Person 2 needs FROM Person 3 (Frontend)

| Needed By | What | Details | Status |
|-----------|------|---------|--------|
| Phase 7+ | WebSocket client | Connect to `WS /ws/pipeline/{job_id}` and render stage events | ❌ Pending |

**Message format Person 3 should expect:**
```json
{
  "resume_id": "uuid-string",
  "stage": "parsing | filtering | graph_ingestion | embedding | hybrid_matching | scoring | completed",
  "status": "in_progress | complete | failed",
  "timestamp": "2026-04-05T12:00:00Z"
}
```

### What Person 2 provides TO others (ready after each phase)

| After Phase | What | Consumer |
|-------------|------|----------|
| Phase 2 | `ResumeParserAgent` — accepts raw file bytes (PDF/DOCX) and returns structured JSON | Person 1's routes |
| Phase 3 | `GraphIngestionAgent.ingest_job(job_id, title, requirements, driver)` — call from job creation | Person 1's `POST /jobs` |
| Phase 4 | `EmbeddingAgent.embed_job(job_id, text, qdrant_client)` — call from job creation | Person 1's `POST /jobs` |
| Phase 6 | `PipelineOrchestrator.run(resume_id, job_id, raw_text)` — full pipeline entry point | Person 1's `POST /resumes` |
| Phase 6 | `FeedbackAgent.run(ctx)` — on-demand feedback generation | Person 1's `POST /feedback` |
| Phase 7 | `WS /ws/pipeline/{job_id}` — real-time WebSocket endpoint | Person 3's UI |

---

## Current State Audit

| Phase | Plan Status | Actual Code State | What's Done | What's Missing |
|-------|-------------|-------------------|-------------|----------------|
| 1 | ✅ Complete | ✅ Done | All skeletons, `config.py`, `base_agent.py`, `pipeline_context.py` | — |
| 2 | ✅ Complete | ✅ Done | PDF/DOCX extraction (`_extract_text`), `PipelineContext.file_bytes`/`filename`, orchestrator updated | — |
| 3 | ✅ Complete | ✅ Done | Neo4j execution in managed transactions, resume ingestion, job ingestion, idempotent MERGE | Needs Docker/Neo4j running for integration tests |
| 4 | ✅ Complete | ✅ Done | Qdrant collection mgmt, `_build_resume_text`, `_ensure_collection`, resume/JD upsert, deterministic UUIDs | Gemini API key needed for real embeddings (mock used in tests) |
| 5 | ❌ Not started | ⚠️ 50% | `ScoringAgent` Gemini call works, `HybridMatchingAgent` has Cypher templates + weights | All graph/vector query execution, score computation, fusion logic |
| 6 | ❌ Not started | ⚠️ 75% | `Orchestrator` fully wired, `FeedbackAgent` Gemini call works | DB persistence stub, feedback stage in orchestrator |
| 7 | ❌ Not started | ❌ Nothing | `StatusCallback` type alias exists in orchestrator | `ws.py` file, `ConnectionManager`, WS route, main.py registration |
| 8 | ❌ Not started | 🔒 Blocked | — | Person 1's DB layer, models, routes |

---

## Phase 2: Finish ResumeParserAgent — PDF/DOCX Extraction

**Goal:** Complete text extraction so the pipeline can accept raw file bytes (PDF/DOCX), not just pre-extracted text.

**Depends on:** Phase 1 only (complete)  
**External dependency:** None

### Tasks

1. **Update `PipelineContext`** (`pipeline_context.py`)
   - Add `file_bytes: bytes = b""` field
   - Add `filename: str = ""` field

2. **Add extraction helper** (`resume_parser_agent.py`)
   - Add `_extract_text(file_bytes: bytes, filename: str) -> str`
   - For `.pdf`: use `PyPDF2.PdfReader` → iterate pages → concatenate `page.extract_text()`
   - For `.docx`: use `docx.Document` → iterate paragraphs → concatenate `paragraph.text`
   - Raise `ValueError` for unsupported extensions

3. **Update `ResumeParserAgent.run(ctx)`**
   - Before existing Gemini call: if `ctx.raw_text` is empty and `ctx.file_bytes` is non-empty, call `_extract_text()`
   - Set `ctx.raw_text` from extraction result
   - Existing Gemini parsing logic remains unchanged

4. **Update `PipelineOrchestrator.run()` signature** (`orchestrator.py`)
   - Add optional `file_bytes: bytes = b""` and `filename: str = ""` parameters
   - Pass them into `PipelineContext` constructor

### Files Modified
- `backend/app/agents/pipeline_context.py`
- `backend/app/agents/resume_parser_agent.py`
- `backend/app/agents/orchestrator.py`

### Stop & Verify Checklist
- [ ] Create a small test script: feed a sample PDF → verify `ctx.raw_text` is populated with readable content
- [ ] Feed a sample DOCX → same verification
- [ ] Feed `raw_text` directly (no `file_bytes`) → existing behavior still works
- [ ] Feed unsupported file type → clean `ValueError`
- [ ] Run `python -c "from app.agents.orchestrator import PipelineOrchestrator"` — no import errors
- [ ] Run Snyk code scan on modified files

### Test Script (save as `backend/test_phase2.py`)
```python
import asyncio
from app.agents.pipeline_context import PipelineContext
from app.agents.resume_parser_agent import ResumeParserAgent

async def test():
    agent = ResumeParserAgent()

    # Test 1: raw_text path (existing behavior)
    ctx = PipelineContext(resume_id="test-1", raw_text="John Doe, Python developer, 5 years experience")
    ctx = await agent.run(ctx)
    assert ctx.parsed_resume, "Parsed resume should not be empty"
    assert not ctx.error, f"Unexpected error: {ctx.error}"
    print("✅ Test 1 passed: raw_text path works")

    # Test 2: file_bytes path (new — use a real PDF/DOCX for this)
    # with open("sample_resume.pdf", "rb") as f:
    #     ctx = PipelineContext(resume_id="test-2", file_bytes=f.read(), filename="sample.pdf")
    #     ctx = await agent.run(ctx)
    #     assert ctx.raw_text, "raw_text should be extracted from PDF"
    #     assert ctx.parsed_resume, "Parsed resume should not be empty"
    #     print("✅ Test 2 passed: PDF extraction works")

asyncio.run(test())
```

---

## Phase 3: GraphIngestionAgent — Neo4j Implementation

**Goal:** Execute the already-defined Cypher templates against a real Neo4j instance.

**Depends on:** Phase 2 (needs `ctx.filtered_resume` structure to be populated)  
**External dependency:** Neo4j running via `docker-compose up rax_neo4j`

### Pre-requisites
```bash
# Start Neo4j
docker-compose up -d rax_neo4j

# Verify Neo4j is reachable
# Browse to http://localhost:7474 — login with neo4j / rax_dev_password
```

### Tasks

1. **Add `neo4j_driver` to orchestrator** (`orchestrator.py`)
   - `PipelineOrchestrator.__init__()` accepts optional `neo4j_driver: AsyncDriver | None`
   - Pass driver to `GraphIngestionAgent` constructor

2. **Implement `GraphIngestionAgent.__init__()`** (`graph_ingestion_agent.py`)
   - Accept `driver: AsyncDriver | None = None`
   - Store as `self._driver`

3. **Implement `run(ctx)` fully** (`graph_ingestion_agent.py`)
   - Open async session: `async with self._driver.session() as session:`
   - Run all Cypher templates inside a transaction:
     - `MERGE_CANDIDATE` with `candidate_id = ctx.resume_id`
     - Loop `ctx.filtered_resume["skills"]` → `MERGE_SKILL` + `LINK_CANDIDATE_SKILL`
     - Loop `ctx.filtered_resume["experience"]` → `MERGE_COMPANY` + `LINK_CANDIDATE_COMPANY`
     - Loop `ctx.filtered_resume["education"]` → `MERGE_EDUCATION`
   - Store returned node ID in `ctx.graph_node_id`

4. **Implement `ingest_job()` class method** (`graph_ingestion_agent.py`)
   - Accept `job_id, title, requirements: dict, driver`
   - Execute `MERGE_JOB` + loop requirements for `LINK_JOB_SKILL`, `LINK_JOB_EDUCATION`

### Files Modified
- `backend/app/agents/graph_ingestion_agent.py`
- `backend/app/agents/orchestrator.py`

### Stop & Verify Checklist
- [ ] Run the agent with sample parsed resume data
- [ ] Open Neo4j browser (localhost:7474) and verify:
  - `MATCH (c:Candidate) RETURN c` → candidate node exists
  - `MATCH (c:Candidate)-[:HAS_SKILL]->(s:Skill) RETURN c.id, s.name` → skill relationships exist
  - `MATCH (c:Candidate)-[:WORKED_AT]->(co:Company) RETURN c.id, co.name` → experience relationships exist
- [ ] Test `ingest_job()` separately — verify Job node + required skill relationships
- [ ] Run full pipeline (Phase 1→2→3) → no errors, `ctx.graph_node_id` is populated
- [ ] Run Snyk code scan on modified files

### Test Script (save as `backend/test_phase3.py`)
```python
import asyncio
from neo4j import AsyncGraphDatabase
from app.agents.graph_ingestion_agent import GraphIngestionAgent
from app.agents.pipeline_context import PipelineContext

async def test():
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "rax_dev_password"))

    agent = GraphIngestionAgent(driver=driver)

    ctx = PipelineContext(resume_id="test-candidate-1", job_id="test-job-1")
    ctx.filtered_resume = {
        "name": "[CANDIDATE_ID]",
        "email": "[REDACTED]",
        "skills": [
            {"name": "Python", "years": 5, "proficiency": "expert"},
            {"name": "FastAPI", "years": 3, "proficiency": "advanced"},
        ],
        "experience": [
            {"title": "Backend Engineer", "company": "TechCorp", "duration": "3 years", "description": "Built APIs"},
        ],
        "education": [
            {"degree": "Bachelor's", "field": "Computer Science", "institution": "[UNIVERSITY]", "year": 2020},
        ],
    }

    ctx = await agent.run(ctx)
    assert not ctx.error, f"Error: {ctx.error}"
    assert ctx.graph_node_id, "graph_node_id should be set"
    print(f"✅ Graph ingestion passed. Node ID: {ctx.graph_node_id}")

    # Test job ingestion
    await agent.ingest_job(
        job_id="test-job-1",
        title="Senior Python Developer",
        requirements={
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "education": "Bachelor's",
            "min_experience_years": 3,
        },
    )
    print("✅ Job ingestion passed")

    await driver.close()

asyncio.run(test())
```

---

## Phase 4: EmbeddingAgent — Qdrant Implementation

**Goal:** Embed resume/JD text via Gemini `text-embedding-004` → upsert into Qdrant vector collections.

**Depends on:** Phase 3 complete (sequential per plan)  
**External dependency:** Qdrant running via `docker-compose up rax_qdrant`, valid `GOOGLE_API_KEY`

### Pre-requisites
```bash
# Start Qdrant
docker-compose up -d rax_qdrant

# Verify Qdrant is reachable
curl http://localhost:6333/healthz    # should return "ok"
# Or browse to http://localhost:6333/dashboard
```

### Tasks

1. **Add `qdrant_client` to orchestrator** (`orchestrator.py`)
   - `PipelineOrchestrator.__init__()` accepts optional `qdrant_client`
   - Pass client to `EmbeddingAgent` constructor

2. **Implement `EmbeddingAgent.__init__()`** (`embedding_agent.py`)
   - Accept `qdrant_client: QdrantClient | None = None`
   - Store as `self._client`

3. **Add `_ensure_collection(collection_name)` helper** (`embedding_agent.py`)
   - Check if collection exists via `self._client.collection_exists()`
   - If not, create with `VectorParams(size=768, distance=Distance.COSINE)`

4. **Implement `run(ctx)` fully** (`embedding_agent.py`)
   - Build embedding text: concatenate skills, experience titles, education from `ctx.filtered_resume`
   - Call `self.embed_text(text)` (inherited from `BaseAgent` — uses `text-embedding-004`)
   - Ensure collection exists
   - Upsert point: `self._client.upsert(collection_name, [PointStruct(id=ctx.resume_id, vector=embedding, payload={...})])`
   - Store point ID in `ctx.qdrant_point_id`

5. **Implement `embed_job()` method** (`embedding_agent.py`)
   - Accept `job_id, description_text, qdrant_client`
   - Embed text → upsert to `JOB_DESCRIPTIONS_COLLECTION`

### Files Modified
- `backend/app/agents/embedding_agent.py`
- `backend/app/agents/orchestrator.py`

### Stop & Verify Checklist
- [ ] Run the agent with sample resume text
- [ ] Open Qdrant dashboard (localhost:6333/dashboard) and verify:
  - `resumes` collection exists with vector size 768
  - A point exists with the test resume_id
- [ ] Test `embed_job()` separately — verify `job_descriptions` collection + point
- [ ] Run full pipeline (Phase 1→2→3→4 parallel) → no errors, both `ctx.graph_node_id` and `ctx.qdrant_point_id` populated
- [ ] Run Snyk code scan on modified files

### Test Script (save as `backend/test_phase4.py`)
```python
import asyncio
from qdrant_client import QdrantClient
from app.agents.embedding_agent import EmbeddingAgent
from app.agents.pipeline_context import PipelineContext

async def test():
    client = QdrantClient(url="http://localhost:6333")

    agent = EmbeddingAgent(qdrant_client=client)

    ctx = PipelineContext(resume_id="test-embed-1", job_id="test-job-1")
    ctx.filtered_resume = {
        "name": "[CANDIDATE_ID]",
        "skills": [
            {"name": "Python", "years": 5, "proficiency": "expert"},
            {"name": "Machine Learning", "years": 3, "proficiency": "advanced"},
        ],
        "experience": [
            {"title": "ML Engineer", "company": "AI Corp", "duration": "3 years", "description": "Built ML pipelines"},
        ],
        "education": [
            {"degree": "Master's", "field": "AI", "institution": "[UNIVERSITY]", "year": 2021},
        ],
    }

    ctx = await agent.run(ctx)
    assert not ctx.error, f"Error: {ctx.error}"
    assert ctx.qdrant_point_id, "qdrant_point_id should be set"
    print(f"✅ Resume embedding passed. Point ID: {ctx.qdrant_point_id}")

    # Test job embedding
    await agent.embed_job(
        job_id="test-job-1",
        description_text="Senior ML Engineer with Python, TensorFlow, 5 years experience",
    )
    print("✅ Job embedding passed")

asyncio.run(test())
```

---

## Phase 5: HybridMatchingAgent — Graph + Vector Fusion

**Goal:** Execute graph traversal (Neo4j) + vector similarity (Qdrant) → compute weighted hybrid score.

**Depends on:** Phases 3 + 4 (graph nodes AND vector points must exist for the test candidate/job)  
**External dependency:** Both Neo4j and Qdrant running with data from Phase 3 + 4 tests

### Pre-requisites
- Phase 3 test data in Neo4j (candidate + job nodes with skill relationships)
- Phase 4 test data in Qdrant (resume + job description embeddings)

### Tasks

1. **Inject `neo4j_driver` + `qdrant_client` into `HybridMatchingAgent`** (`orchestrator.py`)
   - Pass both to `HybridMatchingAgent` constructor

2. **Implement `run(ctx)` fully** (`hybrid_matching_agent.py`)

   **a) Structural Score (Neo4j):**
   - Execute `DIRECT_SKILL_MATCH` Cypher → get `direct_matches` count + `matched_skills` list
   - Execute `SIMILAR_SKILL_MATCH` Cypher → get `similar_matches` count + `similar_skills` list
   - Compute: `structural_score = (direct + 0.5 * similar) / total_required`
   - Collect `skill_gaps` = required skills not matched directly or via similarity

   **b) Semantic Score (Qdrant):**
   - Retrieve resume vector from `RESUMES_COLLECTION` by `ctx.resume_id`
   - Search `JOB_DESCRIPTIONS_COLLECTION` with resume vector → cosine similarity
   - `semantic_score` = top match similarity score (0.0–1.0)

   **c) Experience Score:**
   - Query Neo4j for candidate's years-per-skill vs job's required years
   - `experience_score` = average(min(candidate_years / required_years, 1.0)) across required skills

   **d) Education Score:**
   - Use `EDUCATION_MATCH` Cypher + `DEGREE_LEVELS` dict
   - `education_score` = 1.0 if candidate >= required, else candidate_level / required_level

   **e) Hybrid Fusion:**
   - `hybrid_score = 0.50 * structural + 0.30 * semantic + 0.15 * experience + 0.05 * education`

3. **Populate `ctx.match_result`** with all sub-scores, matched_skills, similar_skills, skill_gaps, graph_paths

4. **ScoringAgent** — no changes needed (already consumes `ctx.match_result` and generates Gemini explanation). Add a `# TODO Phase 8: persist to analyses table` comment if not present.

### Files Modified
- `backend/app/agents/hybrid_matching_agent.py`
- `backend/app/agents/orchestrator.py`

### Stop & Verify Checklist
- [ ] Run HybridMatchingAgent with test data from Phase 3 + 4
- [ ] Verify all sub-scores are non-zero and within 0.0–1.0 range
- [ ] Verify `hybrid_score` matches weighted formula: `0.5*S + 0.3*V + 0.15*E + 0.05*Ed`
- [ ] Verify `matched_skills`, `skill_gaps`, `similar_skills` lists are populated correctly
- [ ] Run full pipeline (1→2→3+4→5→scoring) → `ctx.analysis` has `overall_score`, `explanation`, etc.
- [ ] Run Snyk code scan on modified files

### Test Script (save as `backend/test_phase5.py`)
```python
import asyncio
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from app.agents.hybrid_matching_agent import HybridMatchingAgent
from app.agents.pipeline_context import PipelineContext

async def test():
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "rax_dev_password"))
    qdrant = QdrantClient(url="http://localhost:6333")

    agent = HybridMatchingAgent(neo4j_driver=driver, qdrant_client=qdrant)

    ctx = PipelineContext(
        resume_id="test-candidate-1",  # must exist in Neo4j + Qdrant from Phase 3+4
        job_id="test-job-1",           # must exist in Neo4j + Qdrant from Phase 3+4
    )

    ctx = await agent.run(ctx)
    assert not ctx.error, f"Error: {ctx.error}"
    assert ctx.match_result, "match_result should not be empty"

    mr = ctx.match_result
    print(f"  Structural:  {mr.get('structural_score', 0):.2f}")
    print(f"  Semantic:    {mr.get('semantic_score', 0):.2f}")
    print(f"  Experience:  {mr.get('experience_score', 0):.2f}")
    print(f"  Education:   {mr.get('education_score', 0):.2f}")
    print(f"  Hybrid:      {mr.get('hybrid_score', 0):.2f}")
    print(f"  Matched:     {mr.get('matched_skills', [])}")
    print(f"  Gaps:        {mr.get('skill_gaps', [])}")
    print("✅ Hybrid matching passed")

    await driver.close()

asyncio.run(test())
```

---

## Phase 6: FeedbackAgent Finish + Full Pipeline Verification

**Goal:** Add persistence stub to FeedbackAgent. Optionally add it to orchestrator. Run full end-to-end smoke test.

**Depends on:** Phase 5 (all prior agents must work)  
**External dependency:** None new

### Tasks

1. **FeedbackAgent: add persistence stub** (`feedback_agent.py`)
   - Add `_persist_feedback(resume_id, job_id, feedback_text)` method
   - Implementation: `logger.info("TODO Phase 8: persist feedback for %s", resume_id)` — no-op
   - Call it at end of `run(ctx)` after Gemini generates feedback

2. **Optionally add FeedbackAgent to orchestrator** (`orchestrator.py`)
   - Add as Stage 6 after scoring (runs only if `ctx.analysis` is populated)
   - Follows same `_notify()` pattern: `feedback` stage with `in_progress/complete/failed`

3. **Full end-to-end smoke test**
   - Run `PipelineOrchestrator.run()` with sample resume text
   - Verify all 6 stages complete without error
   - Verify `ctx.analysis` has scores + explanation
   - Verify `ctx.analysis.get("feedback")` is populated (if feedback stage added)

### Files Modified
- `backend/app/agents/feedback_agent.py`
- `backend/app/agents/orchestrator.py`

### Stop & Verify Checklist
- [ ] FeedbackAgent persistence stub logs correctly
- [ ] Full pipeline: `PipelineOrchestrator.run()` → all stages complete ✅
- [ ] `ctx.current_stage == "completed"`
- [ ] `ctx.error is None`
- [ ] `ctx.analysis["overall_score"]` is a number 0–100
- [ ] `ctx.analysis["explanation"]` is a non-empty string
- [ ] StatusCallback (if provided) receives all stage transitions in order
- [ ] Run Snyk code scan on modified files

### Test Script (save as `backend/test_phase6.py`)
```python
import asyncio
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from app.agents.orchestrator import PipelineOrchestrator

async def status_printer(resume_id: str, stage: str, status: str):
    print(f"  [{resume_id}] {stage}: {status}")

async def test():
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "rax_dev_password"))
    qdrant = QdrantClient(url="http://localhost:6333")

    orch = PipelineOrchestrator(
        on_status_change=status_printer,
        neo4j_driver=driver,
        qdrant_client=qdrant,
    )

    ctx = await orch.run(
        resume_id="e2e-test-1",
        job_id="test-job-1",
        raw_text="""
        John Doe — Senior Python Developer
        Skills: Python (5 yrs), FastAPI (3 yrs), PostgreSQL (4 yrs), Docker (2 yrs)
        Experience: Backend Engineer at TechCorp (2020–2023) — Built RESTful APIs serving 10K req/s
        Education: B.S. Computer Science, State University, 2020
        """,
    )

    assert ctx.current_stage == "completed", f"Pipeline did not complete: {ctx.current_stage}, error: {ctx.error}"
    assert ctx.analysis.get("overall_score") is not None, "Missing overall_score"
    print(f"\n✅ Full pipeline passed!")
    print(f"   Overall Score: {ctx.analysis['overall_score']}")
    print(f"   Explanation: {ctx.analysis.get('explanation', 'N/A')[:100]}...")

    await driver.close()

asyncio.run(test())
```

---

## Phase 7: WebSocket Real-Time Broadcasting

**Goal:** Standalone WebSocket endpoint with in-memory pub/sub. Frontend can subscribe to live pipeline progress.

**Depends on:** Phase 6 (orchestrator must support StatusCallback)  
**External dependency:** None (Person 3 can connect to test after this is deployed)

### Tasks

1. **Create package structure**
   - `backend/app/api/__init__.py` (empty)
   - `backend/app/api/routes/__init__.py` (empty)

2. **Create `backend/app/api/routes/ws.py`**
   - `ConnectionManager` class:
     - `_connections: dict[str, list[WebSocket]]` keyed by `job_id`
     - `connect(websocket, job_id)` — accept + register
     - `disconnect(websocket, job_id)` — remove from list
     - `broadcast(job_id, message: dict)` — send JSON to all connected clients for that job
   - WebSocket route:
     ```python
     @router.websocket("/ws/pipeline/{job_id}")
     async def pipeline_ws(websocket: WebSocket, job_id: str):
         await manager.connect(websocket, job_id)
         try:
             while True:
                 await websocket.receive_text()  # keep alive
         except WebSocketDisconnect:
             manager.disconnect(websocket, job_id)
     ```

3. **Create `StatusCallback` factory** (`ws.py`)
   - `make_ws_callback(manager, job_id) -> StatusCallback`
   - Returns an async function that calls `manager.broadcast(job_id, {...})` with ISO timestamp

4. **Register WS router in `main.py`**
   - `from app.api.routes.ws import router as ws_router`
   - `app.include_router(ws_router)`

### Files Created
- `backend/app/api/__init__.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/ws.py`

### Files Modified
- `backend/app/main.py`

### Stop & Verify Checklist
- [ ] Start server: `uvicorn app.main:app --reload`
- [ ] Connect via WebSocket client: `websocat ws://localhost:8000/ws/pipeline/test-job-1`
- [ ] Trigger pipeline (via a test script) → verify JSON stage events appear in WebSocket client
- [ ] Connect 2 clients to same `job_id` → both receive events
- [ ] Disconnect one client → other still receives events, no crashes
- [ ] Connect to different `job_id` → only receives events for that job
- [ ] Run Snyk code scan on modified files

### Info for Person 3 (Frontend)
```
WebSocket URL:  ws://localhost:8000/ws/pipeline/{job_id}
Protocol:       Standard WebSocket (no subprotocol)
Auth:           None (will be added in Phase 8 via query param token)
Messages:       Server → Client only (server pushes JSON events)
Reconnect:      Client should auto-reconnect on disconnect

Event format:
{
  "resume_id": "uuid",
  "stage": "parsing | filtering | graph_ingestion | embedding | hybrid_matching | scoring | completed",
  "status": "in_progress | complete | failed",
  "timestamp": "2026-04-05T12:00:00.000Z"
}
```

---

## Phase 8: Integration with Person 1's Routes (DEFERRED)

**Status:** 🔒 Blocked on Person 1's DB layer  
**Unblocks when:** Person 1 delivers `db/session.py`, `db/neo4j_client.py`, `db/qdrant_client.py`, and SQLAlchemy models.

### Scope (when unblocked)
1. Wire `PipelineOrchestrator.run()` as `BackgroundTask` in `POST /resumes`
2. Wire `EmbeddingAgent.embed_job()` + `GraphIngestionAgent.ingest_job()` in `POST /jobs`
3. Wire `FeedbackAgent.run()` in `POST /feedback`
4. Implement DB persistence in `ScoringAgent` (write to `analyses` table)
5. Implement DB persistence in `FeedbackAgent` (write to `feedback` table)
6. Add WebSocket auth (validate JWT from query param before accepting connection)

---

## Summary: Implementation Order

```
Phase 2 ──► STOP ──► Verify ──► Phase 3 ──► STOP ──► Verify ──► Phase 4 ──► STOP ──► Verify
                                                                                        │
Phase 7 ◄── STOP ◄── Verify ◄── Phase 6 ◄── STOP ◄── Verify ◄── Phase 5 ◄── STOP ◄── Verify
   │
   ▼
 STOP ──► Verify ──► Phase 8 (when Person 1 ready)
```

**Total remaining:** 6 phases (2–7), then Phase 8 after Person 1 delivers.  
**Each phase is self-contained with its own test script and verification checklist.**

---

## Environment Setup Reminder

```bash
# .env file (backend/.env) — required for all phases
GOOGLE_API_KEY=your-gemini-key
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=rax_dev_password
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql+asyncpg://...  # Supabase — needed for Phase 8
SECRET_KEY=your-secret-key

# Start infrastructure (Phases 3+)
docker-compose up -d rax_neo4j rax_qdrant
```
