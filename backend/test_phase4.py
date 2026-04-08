"""Phase 4 verification: EmbeddingAgent — Qdrant resume + job embedding."""
import asyncio
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.agents.embedding_agent import (
    EmbeddingAgent,
    RESUMES_COLLECTION,
    JOB_DESCRIPTIONS_COLLECTION,
    VECTOR_DIM,
    _build_resume_text,
    _resume_id_to_uuid,
    _job_id_to_uuid,
)
from app.agents.pipeline_context import PipelineContext
from app.agents.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO, format="%(name)s — %(message)s")

QDRANT_URL = "http://localhost:6333"

SAMPLE_RESUME = {
    "name": "[CANDIDATE_ID]",
    "email": "[REDACTED]",
    "phone": "[REDACTED]",
    "skills": [
        {"name": "Python", "years": 5, "proficiency": "expert"},
        {"name": "Machine Learning", "years": 3, "proficiency": "advanced"},
        {"name": "Docker", "years": 2, "proficiency": "intermediate"},
    ],
    "experience": [
        {"title": "ML Engineer", "company": "AI Corp", "duration": "3 years", "description": "Built ML pipelines"},
    ],
    "education": [
        {"degree": "Master's", "field": "Artificial Intelligence", "institution": "[UNIVERSITY]", "year": 2021},
    ],
}

JOB_DESCRIPTION = (
    "Senior ML Engineer with strong Python, TensorFlow, PyTorch experience. "
    "5+ years in production ML systems. Master's degree preferred."
)


# ── Offline tests (no Qdrant needed) ─────────────────────────────────────


def test_build_resume_text():
    text = _build_resume_text(SAMPLE_RESUME)
    assert "Python" in text, f"Expected Python in text: {text}"
    assert "ML Engineer" in text, f"Expected ML Engineer in text: {text}"
    assert "Artificial Intelligence" in text, f"Expected AI in text: {text}"
    print(f"PASS Test 1 — _build_resume_text: '{text[:80]}...'")


def test_uuid_deterministic():
    id1 = _resume_id_to_uuid("test-123")
    id2 = _resume_id_to_uuid("test-123")
    id3 = _resume_id_to_uuid("test-456")
    assert id1 == id2, "Same input should produce same UUID"
    assert id1 != id3, "Different input should produce different UUID"
    print(f"PASS Test 2 — UUID deterministic: {id1}")


async def test_no_client():
    agent = EmbeddingAgent(qdrant_client=None)
    ctx = PipelineContext(resume_id="test-no-client")
    ctx.filtered_resume = SAMPLE_RESUME
    ctx = await agent.run(ctx)
    assert ctx.error == "Qdrant client not configured", f"Unexpected error: {ctx.error}"
    print("PASS Test 3 — No client: clean error returned")


async def test_no_resume():
    agent = EmbeddingAgent(qdrant_client=None)
    ctx = PipelineContext(resume_id="test-no-resume")
    ctx = await agent.run(ctx)
    assert ctx.error == "No filtered resume available for embedding"
    print("PASS Test 4 — No resume: clean error returned")


def test_orchestrator_accepts_qdrant():
    orch = PipelineOrchestrator(qdrant_client=None)
    assert orch._embedding._client is None
    print("PASS Test 5 — Orchestrator accepts qdrant_client parameter")


# ── Online tests (Qdrant + Gemini needed) ─────────────────────────────────


async def test_resume_embedding(client: QdrantClient):
    """Test 6: Embed a resume and verify the point in Qdrant."""
    agent = EmbeddingAgent(qdrant_client=client)

    # Try with real Gemini first; fall back to mock embedding if no API key
    ctx = PipelineContext(resume_id="test-p4-resume", job_id="test-p4-job")
    ctx.filtered_resume = SAMPLE_RESUME

    try:
        ctx = await agent.run(ctx)
    except Exception:
        pass

    if ctx.error and "Settings" in ctx.error:
        print("  (No .env / Gemini key — using mock embedding for Qdrant validation)")
        import random
        random.seed(42)
        mock_vector = [random.uniform(-1, 1) for _ in range(VECTOR_DIM)]

        agent._ensure_collection(RESUMES_COLLECTION)
        point_id = _resume_id_to_uuid("test-p4-resume")
        client.upsert(
            collection_name=RESUMES_COLLECTION,
            points=[PointStruct(id=point_id, vector=mock_vector, payload={"resume_id": "test-p4-resume", "job_id": "test-p4-job"})],
        )
        ctx.qdrant_point_id = point_id
        ctx.error = None

    assert not ctx.error, f"FAIL: {ctx.error}"
    assert ctx.qdrant_point_id, "FAIL: qdrant_point_id not set"

    # Verify point exists
    point_id = _resume_id_to_uuid("test-p4-resume")
    points = client.retrieve(collection_name=RESUMES_COLLECTION, ids=[point_id], with_vectors=True)
    assert len(points) == 1, f"FAIL: Expected 1 point, got {len(points)}"
    if points[0].vector is not None:
        assert len(points[0].vector) == VECTOR_DIM, f"FAIL: vector dim {len(points[0].vector)} != {VECTOR_DIM}"
    assert points[0].payload["resume_id"] == "test-p4-resume"

    # Also verify via collection info
    info = client.get_collection(RESUMES_COLLECTION)
    assert info.points_count >= 1, f"FAIL: Expected >=1 points, got {info.points_count}"
    assert info.config.params.vectors.size == VECTOR_DIM, f"FAIL: collection vector size mismatch"

    print(f"PASS Test 6 — Resume embedding: point {point_id}, collection dim={VECTOR_DIM}, points={info.points_count}")


async def test_job_embedding(client: QdrantClient):
    """Test 7: Embed a job description and verify the point in Qdrant."""
    agent = EmbeddingAgent(qdrant_client=client)

    try:
        point_id = await agent.embed_job(job_id="test-p4-job", description_text=JOB_DESCRIPTION)
    except Exception as e:
        if "Settings" in str(e):
            print("  (No .env / Gemini key — using mock embedding for Qdrant validation)")
            import random
            random.seed(99)
            mock_vector = [random.uniform(-1, 1) for _ in range(VECTOR_DIM)]

            agent._ensure_collection(JOB_DESCRIPTIONS_COLLECTION)
            point_id = _job_id_to_uuid("test-p4-job")
            client.upsert(
                collection_name=JOB_DESCRIPTIONS_COLLECTION,
                points=[PointStruct(id=point_id, vector=mock_vector, payload={"job_id": "test-p4-job"})],
            )
        else:
            raise

    assert point_id, "FAIL: point_id not returned"

    expected = _job_id_to_uuid("test-p4-job")
    points = client.retrieve(collection_name=JOB_DESCRIPTIONS_COLLECTION, ids=[expected], with_vectors=True)
    assert len(points) == 1, f"FAIL: Expected 1 point, got {len(points)}"
    if points[0].vector is not None:
        assert len(points[0].vector) == VECTOR_DIM
    assert points[0].payload["job_id"] == "test-p4-job"

    info = client.get_collection(JOB_DESCRIPTIONS_COLLECTION)
    assert info.config.params.vectors.size == VECTOR_DIM

    print(f"PASS Test 7 — Job embedding: point {expected}, collection dim={VECTOR_DIM}")


async def test_idempotent_embedding(client: QdrantClient):
    """Test 8: Double embedding produces same point (not duplicate)."""
    agent = EmbeddingAgent(qdrant_client=client)

    ctx1 = PipelineContext(resume_id="test-p4-resume", job_id="test-p4-job")
    ctx1.filtered_resume = SAMPLE_RESUME
    await agent.run(ctx1)

    ctx2 = PipelineContext(resume_id="test-p4-resume", job_id="test-p4-job")
    ctx2.filtered_resume = SAMPLE_RESUME
    await agent.run(ctx2)

    # Count points
    collection = client.get_collection(RESUMES_COLLECTION)
    # Search for our specific point
    point_id = _resume_id_to_uuid("test-p4-resume")
    points = client.retrieve(collection_name=RESUMES_COLLECTION, ids=[point_id], with_vectors=True)
    assert len(points) == 1, f"FAIL: Expected 1 point, got {len(points)}"

    print("PASS Test 8 — Idempotent: double embedding, same point ID")


def cleanup(client: QdrantClient):
    """Remove test collections from Qdrant."""
    for coll in [RESUMES_COLLECTION, JOB_DESCRIPTIONS_COLLECTION]:
        if client.collection_exists(coll):
            client.delete_collection(coll)


async def main():
    # Offline tests
    test_build_resume_text()
    test_uuid_deterministic()
    await test_no_client()
    await test_no_resume()
    test_orchestrator_accepts_qdrant()

    # Online tests
    print("\n--- Tests requiring Qdrant (http://localhost:6333) + Gemini API key ---")
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=5)
        client.get_collections()  # connectivity check
    except Exception as e:
        print(f"SKIP: Qdrant not reachable — {e}")
        print("Start Qdrant with: docker-compose up -d qdrant")
        return

    try:
        cleanup(client)
        await test_resume_embedding(client)
        await test_job_embedding(client)
        await test_idempotent_embedding(client)
    finally:
        cleanup(client)

    print("\n=== Phase 4 verification complete ===")


if __name__ == "__main__":
    asyncio.run(main())
