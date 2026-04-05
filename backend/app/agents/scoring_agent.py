"""Stage 5: Generate multi-dimensional scores + natural language explanation via Gemini."""

from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an expert hiring evaluator. Given the following hybrid matching context, generate a detailed scoring assessment.

**Job ID:** {job_id}

**Hybrid Match Data (graph + vector analysis):**
{match_result}

**Anonymized Resume (structured):**
{filtered_resume}

Generate a JSON response with this exact schema (no markdown fences):
{{
  "overall_score": <integer 0-100>,
  "skills_score": <integer 0-100>,
  "experience_score": <integer 0-100>,
  "education_score": <integer 0-100>,
  "strengths": ["strength 1", "strength 2", ...],
  "gaps": ["gap 1", "gap 2", ...],
  "explanation": "<2-3 sentence natural language explanation referencing specific skill matches, experience depth, and education fit>"
}}

Base your scores on the hybrid match data. Reference specific graph paths (skill matches, similar skills, gaps) in the explanation.
"""


class ScoringAgent(BaseAgent):
    name = "ScoringAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.current_stage = "scoring"
        logger.info("ScoringAgent: generating scores for resume %s", ctx.resume_id)

        if not ctx.match_result:
            ctx.error = "No match result available for scoring"
            return ctx

        # TODO Phase 5: Full implementation
        #   1. Build prompt with match_result + filtered_resume
        #   2. Call Gemini for explanation generation
        #   3. Parse response JSON
        #   4. Persist to analyses table via SQLAlchemy session

        llm = self.get_llm()
        prompt = SCORING_PROMPT.format(
            job_id=ctx.job_id,
            match_result=json.dumps(ctx.match_result, indent=2),
            filtered_resume=json.dumps(ctx.filtered_resume, indent=2),
        )
        response = await llm.generate_content_async(prompt)

        try:
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            ctx.analysis = json.loads(text)
        except (json.JSONDecodeError, IndexError) as exc:
            logger.error("ScoringAgent: failed to parse response: %s", exc)
            ctx.error = f"Scoring failed: {exc}"

        return ctx
