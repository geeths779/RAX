"""Stage 4: Fuse Neo4j graph traversal + Qdrant cosine similarity into a hybrid score."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from neo4j import AsyncDriver
from qdrant_client import QdrantClient

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

# Default scoring weights (configurable per job)
DEFAULT_WEIGHTS = {
    "structural": 0.50,
    "semantic": 0.30,
    "experience": 0.15,
    "education": 0.05,
}

# ── Cypher templates for matching ─────────────────────────────────────────────

DIRECT_SKILL_MATCH = """
MATCH (j:Job {id: $job_id})-[req:REQUIRES_SKILL]->(s:Skill)<-[has:HAS_SKILL]-(c:Candidate {id: $candidate_id})
RETURN s.name AS skill, req.priority AS priority, req.min_years AS required_years,
       has.years AS candidate_years, has.proficiency AS proficiency
"""

SIMILAR_SKILL_MATCH = """
MATCH (j:Job {id: $job_id})-[:REQUIRES_SKILL]->(required:Skill)
WHERE NOT EXISTS {
    MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(required)
}
MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(has:Skill)-[sim:IS_SIMILAR_TO]->(required)
WHERE sim.score > 0.7
RETURN required.name AS required_skill, has.name AS similar_skill, sim.score AS similarity
"""

REQUIRED_SKILLS_COUNT = """
MATCH (j:Job {id: $job_id})-[:REQUIRES_SKILL]->(s:Skill)
RETURN s.name AS skill
"""

EDUCATION_MATCH = """
MATCH (c:Candidate {id: $candidate_id})-[:HAS_DEGREE]->(ce:Education)
MATCH (j:Job {id: $job_id})-[:REQUIRES_DEGREE]->(je:Education)
RETURN ce.level AS candidate_level, je.level AS required_level, ce.field AS field
"""

# Degree level numeric mapping for comparison
DEGREE_LEVELS = {
    "high school": 1,
    "associate": 2,
    "bachelor": 3,
    "bachelors": 3,
    "bachelor's": 3,
    "master": 4,
    "masters": 4,
    "master's": 4,
    "phd": 5,
    "doctorate": 5,
}

# Qdrant collection names (must match EmbeddingAgent)
RESUMES_COLLECTION = "resumes"
JOB_DESCRIPTIONS_COLLECTION = "job_descriptions"


def _resume_id_to_uuid(resume_id: str) -> str:
    import uuid as _uuid
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"resume:{resume_id}"))


def _job_id_to_uuid(job_id: str) -> str:
    import uuid as _uuid
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"job:{job_id}"))


class HybridMatchingAgent(BaseAgent):
    name = "HybridMatchingAgent"

    def __init__(
        self,
        neo4j_driver: AsyncDriver | None = None,
        qdrant_client: QdrantClient | None = None,
    ):
        self._driver = neo4j_driver
        self._qdrant = qdrant_client

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Compute hybrid score combining graph structural + vector semantic signals."""
        ctx.current_stage = "hybrid_matching"
        logger.info("HybridMatchingAgent: matching resume %s against job %s", ctx.resume_id, ctx.job_id)

        if not ctx.graph_node_id and not ctx.qdrant_point_id:
            logger.warning("HybridMatchingAgent: no graph or vector data — using default scores")
            ctx.match_result = {
                "structural_score": 0.5,
                "semantic_score": 0.5,
                "experience_score": 0.5,
                "education_score": 0.5,
                "hybrid_score": 0.5,
                "matched_skills": [],
                "similar_skills": [],
                "skill_gaps": [],
                "graph_paths": ["No graph/vector data available — using default scores"],
            }
            return ctx

        try:
            # 1. Structural score (Neo4j graph skill matching)
            structural_score, matched_skills, similar_skills, skill_gaps, experience_score, graph_paths = (
                await self._compute_graph_scores(ctx.resume_id, ctx.job_id)
            )

            # 2. Semantic score (Qdrant cosine similarity)
            semantic_score = await self._compute_semantic_score(ctx.resume_id, ctx.job_id)

            # 3. Education score (Neo4j degree comparison)
            education_score = await self._compute_education_score(ctx.resume_id, ctx.job_id)

            # 4. Weighted fusion
            w = DEFAULT_WEIGHTS
            hybrid_score = (
                w["structural"] * structural_score
                + w["semantic"] * semantic_score
                + w["experience"] * experience_score
                + w["education"] * education_score
            )

            ctx.match_result = {
                "structural_score": round(structural_score, 4),
                "semantic_score": round(semantic_score, 4),
                "experience_score": round(experience_score, 4),
                "education_score": round(education_score, 4),
                "hybrid_score": round(hybrid_score, 4),
                "matched_skills": matched_skills,
                "similar_skills": similar_skills,
                "skill_gaps": skill_gaps,
                "graph_paths": graph_paths,
            }

            logger.info(
                "HybridMatchingAgent: scores for %s — structural=%.2f semantic=%.2f exp=%.2f edu=%.2f → hybrid=%.2f",
                ctx.resume_id, structural_score, semantic_score, experience_score, education_score, hybrid_score,
            )
        except Exception as exc:
            logger.error("HybridMatchingAgent: matching failed: %s", exc)
            ctx.error = f"Hybrid matching failed: {exc}"

        return ctx

    # ── Graph-based scoring ───────────────────────────────────────────────

    async def _compute_graph_scores(
        self, candidate_id: str, job_id: str
    ) -> tuple[float, list, list, list, float, list]:
        """Run Neo4j queries for structural + experience scores."""
        matched_skills: list[dict[str, Any]] = []
        similar_skills: list[dict[str, Any]] = []
        skill_gaps: list[str] = []
        graph_paths: list[str] = []

        if not self._driver:
            return 0.5, [], [], [], 0.5, []

        async with self._driver.session() as session:
            # Get all required skills for the job
            req_result = await session.run(REQUIRED_SKILLS_COUNT, job_id=job_id)
            required_skill_names = [r["skill"] async for r in req_result]
            total_required = len(required_skill_names)

            if total_required == 0:
                return 0.5, [], [], [], 0.5, ["No required skills defined for job"]

            # Direct skill matches
            direct_result = await session.run(
                DIRECT_SKILL_MATCH, job_id=job_id, candidate_id=candidate_id
            )
            direct_records = [r async for r in direct_result]

            direct_matched_names: set[str] = set()
            experience_ratios: list[float] = []

            for rec in direct_records:
                skill_name = rec["skill"]
                direct_matched_names.add(skill_name)
                matched_skills.append({
                    "skill": skill_name,
                    "candidate_years": rec["candidate_years"],
                    "required_years": rec["required_years"],
                    "proficiency": rec["proficiency"],
                })
                graph_paths.append(f"Candidate -[:HAS_SKILL]-> {skill_name} <-[:REQUIRES_SKILL]- Job")

                # Experience ratio per skill
                req_years = rec["required_years"] or 0
                cand_years = rec["candidate_years"] or 0
                if req_years > 0:
                    experience_ratios.append(min(cand_years / req_years, 1.0))

            # Similar skill matches (partial credit)
            similar_result = await session.run(
                SIMILAR_SKILL_MATCH, job_id=job_id, candidate_id=candidate_id
            )
            similar_records = [r async for r in similar_result]
            similar_matched_names: set[str] = set()

            for rec in similar_records:
                similar_matched_names.add(rec["required_skill"])
                similar_skills.append({
                    "required_skill": rec["required_skill"],
                    "similar_skill": rec["similar_skill"],
                    "similarity": rec["similarity"],
                })
                graph_paths.append(
                    f"Candidate -[:HAS_SKILL]-> {rec['similar_skill']} "
                    f"-[:IS_SIMILAR_TO]-> {rec['required_skill']} <-[:REQUIRES_SKILL]- Job"
                )

            # Skill gaps (required but neither directly nor similarly matched)
            for skill_name in required_skill_names:
                if skill_name not in direct_matched_names and skill_name not in similar_matched_names:
                    skill_gaps.append(skill_name)

            # Structural score: direct matches + 0.5 * similar matches / total
            structural_score = min(
                (len(direct_matched_names) + 0.5 * len(similar_matched_names)) / total_required,
                1.0,
            )

            # Experience score: avg of per-skill year ratios (default 0.5 if no data)
            experience_score = (
                sum(experience_ratios) / len(experience_ratios)
                if experience_ratios
                else 0.5
            )

        return structural_score, matched_skills, similar_skills, skill_gaps, experience_score, graph_paths

    # ── Vector-based scoring ──────────────────────────────────────────────

    async def _compute_semantic_score(self, resume_id: str, job_id: str) -> float:
        """Compute cosine similarity between resume vector and job description vector in Qdrant."""
        if not self._qdrant:
            return 0.5

        try:
            resume_point_id = _resume_id_to_uuid(resume_id)
            job_point_id = _job_id_to_uuid(job_id)

            # Retrieve resume vector (wrapped in to_thread — sync Qdrant client)
            resume_points = await asyncio.to_thread(
                self._qdrant.retrieve,
                collection_name=RESUMES_COLLECTION,
                ids=[resume_point_id],
                with_vectors=True,
            )
            if not resume_points or not resume_points[0].vector:
                logger.warning("No resume vector found for %s", resume_id)
                return 0.5

            resume_vector = resume_points[0].vector

            # Search job_descriptions collection with resume vector
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            search_results = await asyncio.to_thread(
                self._qdrant.query_points,
                collection_name=JOB_DESCRIPTIONS_COLLECTION,
                query=resume_vector,
                limit=5,
            )

            # Find the score for the target job
            for hit in search_results.points:
                if hit.payload and hit.payload.get("job_id") == job_id:
                    return max(0.0, min(hit.score, 1.0))

            # Target job not in top-5 — return low default, not an unrelated job's score
            return 0.3
        except Exception as exc:
            logger.warning("Semantic score computation failed: %s", exc)
            return 0.5

    # ── Education scoring ─────────────────────────────────────────────────

    async def _compute_education_score(self, candidate_id: str, job_id: str) -> float:
        """Compare candidate's education level against job requirements via Neo4j."""
        if not self._driver:
            return 0.5

        try:
            async with self._driver.session() as session:
                result = await session.run(
                    EDUCATION_MATCH, candidate_id=candidate_id, job_id=job_id
                )
                records = [r async for r in result]

            if not records:
                return 0.5

            best_score = 0.0
            for rec in records:
                cand_level = DEGREE_LEVELS.get(str(rec["candidate_level"]).lower().strip(), 0)
                req_level = DEGREE_LEVELS.get(str(rec["required_level"]).lower().strip(), 0)
                if req_level > 0:
                    score = min(cand_level / req_level, 1.0)
                else:
                    score = 1.0
                best_score = max(best_score, score)

            return best_score
        except Exception as exc:
            logger.warning("Education score computation failed: %s", exc)
            return 0.5
