"""Phase 3 verification: GraphIngestionAgent — Neo4j resume + job ingestion."""
import asyncio
import logging

from neo4j import AsyncGraphDatabase

from app.agents.graph_ingestion_agent import GraphIngestionAgent
from app.agents.pipeline_context import PipelineContext
from app.agents.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO, format="%(name)s — %(message)s")

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "rax_dev_password")

SAMPLE_RESUME = {
    "name": "[CANDIDATE_ID]",
    "email": "[REDACTED]",
    "phone": "[REDACTED]",
    "skills": [
        {"name": "Python", "years": 5, "proficiency": "expert"},
        {"name": "FastAPI", "years": 3, "proficiency": "advanced"},
        {"name": "Docker", "years": 2, "proficiency": "intermediate"},
    ],
    "experience": [
        {"title": "Backend Engineer", "company": "TechCorp", "duration": "3 years", "description": "Built APIs"},
        {"title": "Junior Dev", "company": "StartupXYZ", "duration": "1 year", "description": "Full-stack work"},
    ],
    "education": [
        {"degree": "Bachelor's", "field": "Computer Science", "institution": "[UNIVERSITY]", "year": 2020},
    ],
}

SAMPLE_JOB_REQUIREMENTS = {
    "skills": [
        {"name": "Python", "priority": "required", "min_years": 3},
        {"name": "FastAPI", "priority": "required", "min_years": 2},
        {"name": "PostgreSQL", "priority": "preferred", "min_years": 1},
    ],
    "education": "Bachelor's",
    "field": "Computer Science",
    "min_education_level": 3,
}


async def cleanup(driver):
    """Remove test data from Neo4j."""
    async with driver.session() as session:
        await session.run("MATCH (n) WHERE n.id IN ['test-p3-candidate', 'test-p3-job'] DETACH DELETE n")


async def test_resume_ingestion(driver):
    """Test 1: Ingest a resume and verify nodes + relationships."""
    agent = GraphIngestionAgent(driver=driver)
    ctx = PipelineContext(resume_id="test-p3-candidate", job_id="test-p3-job")
    ctx.filtered_resume = SAMPLE_RESUME

    ctx = await agent.run(ctx)
    assert not ctx.error, f"FAIL: {ctx.error}"
    assert ctx.graph_node_id, "FAIL: graph_node_id not set"

    # Verify nodes exist
    async with driver.session() as session:
        # Check candidate
        r = await session.run("MATCH (c:Candidate {id: 'test-p3-candidate'}) RETURN c.id AS id")
        record = await r.single()
        assert record, "FAIL: Candidate node not found"

        # Check skills
        r = await session.run(
            "MATCH (c:Candidate {id: 'test-p3-candidate'})-[r:HAS_SKILL]->(s:Skill) "
            "RETURN s.name AS name, r.years AS years ORDER BY s.name"
        )
        skills = [rec async for rec in r]
        skill_names = [s["name"] for s in skills]
        assert "Python" in skill_names, f"FAIL: Python not in skills: {skill_names}"
        assert "FastAPI" in skill_names, f"FAIL: FastAPI not in skills: {skill_names}"
        assert "Docker" in skill_names, f"FAIL: Docker not in skills: {skill_names}"
        assert len(skills) == 3, f"FAIL: Expected 3 skills, got {len(skills)}"

        # Check experience
        r = await session.run(
            "MATCH (c:Candidate {id: 'test-p3-candidate'})-[:WORKED_AT]->(co:Company) "
            "RETURN co.name AS name ORDER BY co.name"
        )
        companies = [rec["name"] async for rec in r]
        assert "TechCorp" in companies, f"FAIL: TechCorp not in companies: {companies}"
        assert "StartupXYZ" in companies, f"FAIL: StartupXYZ not in companies: {companies}"

        # Check education
        r = await session.run(
            "MATCH (c:Candidate {id: 'test-p3-candidate'})-[:HAS_DEGREE]->(e:Education) "
            "RETURN e.level AS degree, e.field AS field"
        )
        edu = await r.single()
        assert edu, "FAIL: Education node not found"
        assert edu["degree"] == "Bachelor's", f"FAIL: degree mismatch: {edu['degree']}"

    print("PASS Test 1 — Resume ingestion: Candidate + 3 skills + 2 companies + 1 education")


async def test_job_ingestion(driver):
    """Test 2: Ingest a job and verify Job node + required skills."""
    agent = GraphIngestionAgent(driver=driver)

    await agent.ingest_job(
        job_id="test-p3-job",
        title="Senior Python Developer",
        requirements=SAMPLE_JOB_REQUIREMENTS,
    )

    async with driver.session() as session:
        # Check job node
        r = await session.run("MATCH (j:Job {id: 'test-p3-job'}) RETURN j.title AS title")
        record = await r.single()
        assert record, "FAIL: Job node not found"
        assert record["title"] == "Senior Python Developer"

        # Check required skills
        r = await session.run(
            "MATCH (j:Job {id: 'test-p3-job'})-[r:REQUIRES_SKILL]->(s:Skill) "
            "RETURN s.name AS name, r.priority AS priority, r.min_years AS min_years ORDER BY s.name"
        )
        req_skills = [rec async for rec in r]
        names = [s["name"] for s in req_skills]
        assert "Python" in names, f"FAIL: Python not in required skills: {names}"
        assert "FastAPI" in names, f"FAIL: FastAPI not in required skills: {names}"
        assert "PostgreSQL" in names, f"FAIL: PostgreSQL not in required skills: {names}"

        # Check education requirement
        r = await session.run(
            "MATCH (j:Job {id: 'test-p3-job'})-[:REQUIRES_DEGREE]->(e:Education) "
            "RETURN e.level AS degree"
        )
        edu = await r.single()
        assert edu, "FAIL: Job education requirement not found"

    print("PASS Test 2 — Job ingestion: Job node + 3 required skills + 1 education requirement")


async def test_no_driver():
    """Test 3: Agent without driver returns clean error."""
    agent = GraphIngestionAgent(driver=None)
    ctx = PipelineContext(resume_id="test-no-driver")
    ctx.filtered_resume = SAMPLE_RESUME

    ctx = await agent.run(ctx)
    assert ctx.error == "Neo4j driver not configured", f"FAIL: unexpected error: {ctx.error}"
    print("PASS Test 3 — No driver: clean error message returned")


async def test_no_resume():
    """Test 4: Agent with empty filtered_resume returns clean error."""
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    agent = GraphIngestionAgent(driver=driver)
    ctx = PipelineContext(resume_id="test-empty")

    ctx = await agent.run(ctx)
    assert ctx.error == "No filtered resume available for graph ingestion"
    await driver.close()
    print("PASS Test 4 — No resume: clean error message returned")


async def test_orchestrator_accepts_driver():
    """Test 5: Orchestrator constructor accepts neo4j_driver parameter."""
    orch = PipelineOrchestrator(neo4j_driver=None)
    assert orch._graph_ingestion._driver is None
    print("PASS Test 5 — Orchestrator accepts neo4j_driver parameter")


async def test_idempotent_ingestion(driver):
    """Test 6: Running ingestion twice doesn't duplicate nodes (MERGE behavior)."""
    agent = GraphIngestionAgent(driver=driver)
    ctx = PipelineContext(resume_id="test-p3-candidate", job_id="test-p3-job")
    ctx.filtered_resume = SAMPLE_RESUME

    # Run twice
    await agent.run(ctx)
    ctx2 = PipelineContext(resume_id="test-p3-candidate", job_id="test-p3-job")
    ctx2.filtered_resume = SAMPLE_RESUME
    await agent.run(ctx2)

    async with driver.session() as session:
        r = await session.run(
            "MATCH (c:Candidate {id: 'test-p3-candidate'}) RETURN count(c) AS cnt"
        )
        record = await r.single()
        assert record["cnt"] == 1, f"FAIL: Expected 1 candidate, got {record['cnt']} (MERGE not working)"

    print("PASS Test 6 — Idempotent: double ingestion produces 1 candidate node")


async def main():
    # Test without Neo4j first
    await test_no_driver()

    # Tests requiring Neo4j
    print("\n--- Tests requiring Neo4j (bolt://localhost:7687) ---")
    try:
        driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        await driver.verify_connectivity()
    except Exception as e:
        print(f"SKIP: Neo4j not reachable — {e}")
        print("Start Neo4j with: docker-compose up -d rax_neo4j")
        return

    try:
        await cleanup(driver)
        await test_no_resume()
        await test_orchestrator_accepts_driver()
        await test_resume_ingestion(driver)
        await test_job_ingestion(driver)
        await test_idempotent_ingestion(driver)
    finally:
        await cleanup(driver)
        await driver.close()

    print("\n=== Phase 3 verification complete ===")


if __name__ == "__main__":
    asyncio.run(main())
