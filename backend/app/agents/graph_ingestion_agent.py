"""Stage 3a: Decompose parsed resume into Neo4j knowledge graph nodes and relationships."""

from __future__ import annotations

import logging

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

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Ingest a candidate's parsed resume into the Neo4j knowledge graph."""
        ctx.current_stage = "graph_ingestion"
        logger.info("GraphIngestionAgent: ingesting resume %s into Neo4j", ctx.resume_id)

        if not ctx.filtered_resume:
            ctx.error = "No filtered resume available for graph ingestion"
            return ctx

        # TODO Phase 3: Implement actual Neo4j session calls
        #   neo4j_session = get_neo4j_session()
        #   async with neo4j_session as session:
        #       await session.run(MERGE_CANDIDATE, ...)
        #       for skill in ctx.filtered_resume["skills"]:
        #           await session.run(LINK_CANDIDATE_SKILL, ...)
        #       for exp in ctx.filtered_resume["experience"]:
        #           await session.run(LINK_CANDIDATE_COMPANY, ...)
        #       for edu in ctx.filtered_resume["education"]:
        #           await session.run(MERGE_EDUCATION, ...)

        ctx.graph_node_id = ctx.resume_id  # placeholder
        return ctx

    async def ingest_job(self, job_id: str, title: str, requirements: dict) -> None:
        """Ingest a job description's requirements into Neo4j. Called from jobs route."""
        logger.info("GraphIngestionAgent: ingesting job %s into Neo4j", job_id)
        # TODO Phase 3: Implement
        #   MERGE Job node, LINK_JOB_SKILL for each required skill,
        #   LINK_JOB_EDUCATION for degree requirements
