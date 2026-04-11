"""On-demand: Generate constructive feedback for rejected candidates via Gemini."""

from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

FEEDBACK_PROMPT = """You are a professional HR communication specialist. Write a constructive, encouraging feedback email for a candidate who was not selected.

**Candidate's matched skills:** {matched_skills}
**Candidate's skill gaps:** {skill_gaps}
**Similar skills they have:** {similar_skills}
**Overall assessment:** {explanation}

Guidelines:
- 150-200 words maximum
- Professional and empathetic tone
- Reference specific skills they demonstrated well
- Suggest 1-2 concrete areas for improvement based on gaps
- Do NOT mention the candidate's name or any identifying information
- End with encouragement

Return ONLY the email body text (no subject line, no JSON).
"""


class FeedbackAgent(BaseAgent):
    name = "FeedbackAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Generate feedback based on the scoring analysis. Called on-demand, not in main pipeline."""
        logger.info("FeedbackAgent: generating feedback for resume %s", ctx.resume_id)

        if not ctx.analysis:
            ctx.error = "No analysis available for feedback generation"
            return ctx

        # TODO Phase 6: Full implementation
        #   1. Extract match details from ctx.match_result + ctx.analysis
        #   2. Call Gemini with FEEDBACK_PROMPT
        #   3. Persist to feedback table via SQLAlchemy session

        prompt = FEEDBACK_PROMPT.format(
            matched_skills=json.dumps(ctx.match_result.get("matched_skills", [])),
            skill_gaps=json.dumps(ctx.match_result.get("skill_gaps", [])),
            similar_skills=json.dumps(ctx.match_result.get("similar_skills", [])),
            explanation=ctx.analysis.get("explanation", ""),
        )

        try:
            feedback_text = await self.call_llm(prompt)
        except RuntimeError as exc:
            logger.error("FeedbackAgent: Gemini call failed: %s", exc)
            ctx.error = str(exc)
            return ctx

        # Store in ctx for caller to persist
        ctx.analysis["feedback"] = feedback_text
        return ctx
