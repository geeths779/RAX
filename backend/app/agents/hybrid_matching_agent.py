"""Stage 4: Fuse Neo4j graph traversal + Qdrant cosine similarity into a hybrid score."""

from __future__ import annotations

import logging

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
    "master": 4,
    "masters": 4,
    "phd": 5,
    "doctorate": 5,
}


class HybridMatchingAgent(BaseAgent):
    name = "HybridMatchingAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Compute hybrid score combining graph structural + vector semantic signals."""
        ctx.current_stage = "hybrid_matching"
        logger.info("HybridMatchingAgent: matching resume %s against job %s", ctx.resume_id, ctx.job_id)

        if not ctx.graph_node_id or not ctx.qdrant_point_id:
            ctx.error = "Graph or vector data missing for hybrid matching"
            return ctx

        # TODO Phase 5: Full implementation
        #   1. Run DIRECT_SKILL_MATCH and SIMILAR_SKILL_MATCH Cypher queries
        #   2. Compute structural_score from matched/total skills (with partial credit)
        #   3. Compute experience_score from years comparison per skill
        #   4. Compute education_score from degree level comparison
        #   5. Query Qdrant: cosine_similarity(resume_vector, jd_vector) → semantic_score
        #   6. Fuse: hybrid = w.structural*structural + w.semantic*semantic
        #                    + w.experience*experience + w.education*education
        #   7. Auto-enrich: if Qdrant finds similar skills without IS_SIMILAR_TO edge → create it

        ctx.match_result = {
            "structural_score": 0.0,
            "semantic_score": 0.0,
            "experience_score": 0.0,
            "education_score": 0.0,
            "hybrid_score": 0.0,
            "matched_skills": [],
            "similar_skills": [],
            "skill_gaps": [],
            "graph_paths": [],
        }
        return ctx
