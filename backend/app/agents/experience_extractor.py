"""LLM Judge: Extract precise experience metadata from raw resume text."""

from __future__ import annotations

import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are an expert resume analyst. Your ONLY job is to extract accurate experience information from the resume text below.

**Resume text:**
---
{resume_text}
---

**Already-parsed experience entries (may have inaccurate durations):**
{parsed_experience}

INSTRUCTIONS:
1. Read the actual resume text carefully. Look for date ranges (e.g. "Jan 2019 – Present", "2017-2021"), durations mentioned explicitly ("5 years of experience in…"), and any other time indicators.
2. Calculate total_years_experience by summing all distinct employment periods (account for overlaps).
3. For each skill listed, estimate years based on when it first appeared in experience entries.
4. Determine seniority_level from job titles and total experience: intern (<1yr), junior (1-3yr), mid (3-6yr), senior (6-10yr), lead/staff (10-15yr), principal/director (15+yr).
5. Fix each experience entry's duration to be accurate (e.g. "2 years 3 months" or "Jan 2019 – Mar 2021").

Return ONLY valid JSON (no markdown fences):
{{
  "total_years_experience": <float, e.g. 5.5>,
  "seniority_level": "<intern|junior|mid|senior|lead|staff|principal|director>",
  "experience_entries": [
    {{
      "title": "string",
      "company": "string",
      "start_date": "string (e.g. Jan 2019 or 2019)",
      "end_date": "string (e.g. Mar 2021 or Present)",
      "duration_months": <integer>,
      "key_technologies": ["string"]
    }}
  ],
  "skill_experience": [
    {{
      "skill": "string",
      "estimated_years": <float>,
      "evidence": "brief reason"
    }}
  ]
}}

Be precise. If dates are ambiguous, make your best estimate and note it. Do NOT inflate or guess — use only what the resume text supports.
"""


class ExperienceExtractorAgent(BaseAgent):
    name = "ExperienceExtractorAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("ExperienceExtractorAgent: extracting experience for resume %s", ctx.resume_id)

        if not ctx.raw_text:
            logger.warning("ExperienceExtractorAgent: no raw text — skipping")
            return ctx

        parsed_exp = ctx.parsed_resume.get("experience", [])

        prompt = EXTRACT_PROMPT.format(
            resume_text=ctx.raw_text[:15000],
            parsed_experience=json.dumps(parsed_exp, indent=2),
        )

        try:
            text = await self.call_llm(prompt)
            extracted = json.loads(text)

            ctx.enriched_experience = extracted

            # Patch parsed_resume with accurate data
            if "experience" in ctx.parsed_resume and extracted.get("experience_entries"):
                entries = extracted["experience_entries"]
                for i, entry in enumerate(ctx.parsed_resume["experience"]):
                    if i < len(entries):
                        src = entries[i]
                        start = src.get("start_date", "")
                        end = src.get("end_date", "")
                        months = src.get("duration_months", 0)
                        if start and end:
                            entry["duration"] = f"{start} – {end} ({months} months)"
                        elif months:
                            entry["duration"] = f"{months} months"

            # Patch skill years from skill_experience
            skill_years_map = {
                s["skill"].lower(): s["estimated_years"]
                for s in extracted.get("skill_experience", [])
            }
            for skill in ctx.parsed_resume.get("skills", []):
                name_lower = skill.get("name", "").lower()
                if name_lower in skill_years_map:
                    skill["years"] = skill_years_map[name_lower]

            logger.info(
                "ExperienceExtractorAgent: total_years=%.1f, seniority=%s, %d skill estimates",
                extracted.get("total_years_experience", 0),
                extracted.get("seniority_level", "unknown"),
                len(extracted.get("skill_experience", [])),
            )
        except (json.JSONDecodeError, IndexError) as exc:
            logger.warning("ExperienceExtractorAgent: parse failed (non-fatal): %s", exc)
        except RuntimeError as exc:
            logger.warning("ExperienceExtractorAgent: LLM call failed (non-fatal): %s", exc)

        return ctx
