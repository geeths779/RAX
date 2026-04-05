"""Stage 2: Anonymize parsed resume — remove name, gender, institution, nationality signals."""

from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

BIAS_FILTER_PROMPT = """You are a bias-removal agent. Given the following parsed resume JSON, return a new JSON with these anonymizations applied:

1. Replace the "name" field with "[CANDIDATE_ID]"
2. Replace every "institution" value with "[UNIVERSITY]"
3. Remove any gender indicators (he/she/him/her pronouns, gendered titles like Mr./Ms./Mrs.)
4. Remove any nationality or ethnicity indicators
5. Remove any age indicators (date of birth, graduation year that reveals age)
6. Keep ALL skills, experience details, and education degree/field intact — only remove identity signals

Return ONLY valid JSON (no markdown fences). Preserve the exact same schema as the input.

Input JSON:
{resume_json}
"""


class BiasFilterAgent(BaseAgent):
    name = "BiasFilterAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.current_stage = "filtering"
        logger.info("BiasFilterAgent: anonymizing resume %s", ctx.resume_id)

        if not ctx.parsed_resume:
            ctx.error = "No parsed resume available for bias filtering"
            return ctx

        llm = self.get_llm()
        prompt = BIAS_FILTER_PROMPT.format(
            resume_json=json.dumps(ctx.parsed_resume, indent=2)
        )
        response = await llm.generate_content_async(prompt)

        try:
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            ctx.filtered_resume = json.loads(text)
        except (json.JSONDecodeError, IndexError) as exc:
            logger.error("BiasFilterAgent: failed to parse response: %s", exc)
            ctx.error = f"Bias filtering failed: {exc}"

        return ctx
