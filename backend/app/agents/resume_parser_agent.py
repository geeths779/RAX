"""Stage 1: Extract raw text from PDF/DOCX and parse into structured JSON via Gemini."""

from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

PARSE_PROMPT = """You are a resume parser. Extract structured data from the following resume text.

Return ONLY valid JSON with this exact schema (no markdown fences):
{
  "name": "string",
  "email": "string",
  "phone": "string",
  "skills": [{"name": "string", "years": integer_or_0, "proficiency": "beginner|intermediate|expert"}],
  "experience": [{"title": "string", "company": "string", "duration": "string", "description": "string"}],
  "education": [{"degree": "string", "field": "string", "institution": "string", "year": integer_or_0}]
}

If a field is unknown, use empty string or 0. Do not invent data.

Resume text:
---
{resume_text}
---
"""


class ResumeParserAgent(BaseAgent):
    name = "ResumeParserAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.current_stage = "parsing"
        logger.info("ResumeParserAgent: starting parse for resume %s", ctx.resume_id)

        # TODO Phase 2: Extract raw text from file bytes (PDF/DOCX)
        #   - PyPDF2 for PDF, python-docx for DOCX
        #   - For now, expects ctx.raw_text to be pre-populated

        if not ctx.raw_text:
            ctx.error = "No raw text available for parsing"
            return ctx

        llm = self.get_llm()
        prompt = PARSE_PROMPT.format(resume_text=ctx.raw_text[:15000])  # truncate safety
        response = await llm.generate_content_async(prompt)

        try:
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            ctx.parsed_resume = json.loads(text)
        except (json.JSONDecodeError, IndexError) as exc:
            logger.error("ResumeParserAgent: failed to parse Gemini response: %s", exc)
            ctx.error = f"Resume parsing failed: {exc}"

        return ctx
