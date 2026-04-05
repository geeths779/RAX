"""Stage 3a: Decompose parsed resume into Neo4j knowledge graph nodes and relationships."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncManagedTransaction

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

# ── Cypher templates ──────────────────────────────────────────────────────────

MERGE_CANDIDATE = """
MERGE (c:Candidate {id: $candidate_id})
SET c.anonymized_name = $name
RETURN c.id AS node_id
"""

MERGE_SKILL = """
MERGE (s:Skill {name: $skill_name})
RETURN s.name
"""

LINK_CANDIDATE_SKILL = """
MATCH (c:Candidate {id: $candidate_id})
MERGE (s:Skill {name: $skill_name})
MERGE (c)-[r:HAS_SKILL]->(s)
SET r.years = $years, r.proficiency = $proficiency
"""

MERGE_COMPANY = """
MERGE (co:Company {name: $company_name})
RETURN co.name
"""

LINK_CANDIDATE_COMPANY = """
MATCH (c:Candidate {id: $candidate_id})
MERGE (co:Company {name: $company_name})
MERGE (c)-[r:WORKED_AT]->(co)
SET r.duration = $duration, r.title = $title
"""

MERGE_EDUCATION = """
MATCH (c:Candidate {id: $candidate_id})
MERGE (e:Education {level: $degree, field: $field})
MERGE (c)-[:HAS_DEGREE]->(e)
MERGE (i:Institution {name: $institution})
MERGE (c)-[:STUDIED_AT]->(i)
"""

MERGE_JOB = """
MERGE (j:Job {id: $job_id})
SET j.title = $title
RETURN j.id
"""

LINK_JOB_SKILL = """
MATCH (j:Job {id: $job_id})
MERGE (s:Skill {name: $skill_name})
MERGE (j)-[r:REQUIRES_SKILL]->(s)
SET r.priority = $priority, r.min_years = $min_years
"""

LINK_JOB_EDUCATION = """
MATCH (j:Job {id: $job_id})
MERGE (e:Education {level: $degree, field: $field})
MERGE (j)-[r:REQUIRES_DEGREE]->(e)
SET r.min_level = $min_level
"""


class GraphIngestionAgent(BaseAgent):
    name = "GraphIngestionAgent"

    def __init__(self, driver: AsyncDriver | None = None):
        self._driver = driver

    # ── Resume ingestion ──────────────────────────────────────────────────

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Ingest a candidate's parsed resume into the Neo4j knowledge graph."""
        ctx.current_stage = "graph_ingestion"
        logger.info("GraphIngestionAgent: ingesting resume %s into Neo4j", ctx.resume_id)

        if not ctx.filtered_resume:
            ctx.error = "No filtered resume available for graph ingestion"
            return ctx

        if not self._driver:
            ctx.error = "Neo4j driver not configured"
            return ctx

        try:
            async with self._driver.session() as session:
                node_id = await session.execute_write(
                    self._ingest_resume_tx, ctx.resume_id, ctx.filtered_resume
                )
            ctx.graph_node_id = node_id
            logger.info("GraphIngestionAgent: created graph node %s for resume %s", node_id, ctx.resume_id)
        except Exception as exc:
            logger.error("GraphIngestionAgent: Neo4j ingestion failed: %s", exc)
            ctx.error = f"Graph ingestion failed: {exc}"

        return ctx

    @staticmethod
    async def _ingest_resume_tx(
        tx: AsyncManagedTransaction,
        candidate_id: str,
        resume: dict[str, Any],
    ) -> str:
        """Execute all Cypher writes for a single resume inside one transaction."""

        # 1. Create/merge the Candidate node
        result = await tx.run(
            MERGE_CANDIDATE,
            candidate_id=candidate_id,
            name=resume.get("name", "[CANDIDATE_ID]"),
        )
        record = await result.single()
        node_id = record["node_id"] if record else candidate_id

        # 2. Skills
        for skill in resume.get("skills", []):
            await tx.run(
                LINK_CANDIDATE_SKILL,
                candidate_id=candidate_id,
                skill_name=skill.get("name", ""),
                years=skill.get("years", 0),
                proficiency=skill.get("proficiency", ""),
            )

        # 3. Experience / Companies
        for exp in resume.get("experience", []):
            await tx.run(
                LINK_CANDIDATE_COMPANY,
                candidate_id=candidate_id,
                company_name=exp.get("company", "Unknown"),
                duration=exp.get("duration", ""),
                title=exp.get("title", ""),
            )

        # 4. Education
        for edu in resume.get("education", []):
            await tx.run(
                MERGE_EDUCATION,
                candidate_id=candidate_id,
                degree=edu.get("degree", ""),
                field=edu.get("field", ""),
                institution=edu.get("institution", "[UNIVERSITY]"),
            )

        return node_id

    # ── Job ingestion (called independently from jobs route) ──────────────

    async def ingest_job(self, job_id: str, title: str, requirements: dict[str, Any]) -> None:
        """Ingest a job description's requirements into Neo4j. Called from jobs route."""
        logger.info("GraphIngestionAgent: ingesting job %s into Neo4j", job_id)

        if not self._driver:
            raise RuntimeError("Neo4j driver not configured")

        async with self._driver.session() as session:
            await session.execute_write(
                self._ingest_job_tx, job_id, title, requirements
            )

        logger.info("GraphIngestionAgent: job %s ingested successfully", job_id)

    @staticmethod
    async def _ingest_job_tx(
        tx: AsyncManagedTransaction,
        job_id: str,
        title: str,
        requirements: dict[str, Any],
    ) -> None:
        """Execute all Cypher writes for a job inside one transaction."""

        # 1. Create/merge the Job node
        await tx.run(MERGE_JOB, job_id=job_id, title=title)

        # 2. Required skills
        for skill in requirements.get("skills", []):
            # Support both simple strings and dicts with metadata
            if isinstance(skill, str):
                skill_name, priority, min_years = skill, "required", 0
            else:
                skill_name = skill.get("name", "")
                priority = skill.get("priority", "required")
                min_years = skill.get("min_years", 0)

            await tx.run(
                LINK_JOB_SKILL,
                job_id=job_id,
                skill_name=skill_name,
                priority=priority,
                min_years=min_years,
            )

        # 3. Education requirements
        education = requirements.get("education", "")
        if education:
            edu_field = requirements.get("field", "")
            degree = education if isinstance(education, str) else education.get("degree", "")
            field = edu_field if isinstance(edu_field, str) else ""
            min_level = requirements.get("min_education_level", 1)

            await tx.run(
                LINK_JOB_EDUCATION,
                job_id=job_id,
                degree=degree,
                field=field,
                min_level=min_level,
            )
