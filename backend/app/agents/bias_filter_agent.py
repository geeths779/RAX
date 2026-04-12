"""Stage 2: Anonymize parsed resume — deterministic (no LLM).

Removes name, gender signals, institution names, and nationality/age indicators
via direct field manipulation. Much faster than an LLM call (~0ms vs ~5-15s).
"""

from __future__ import annotations

import copy
import logging
import re

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

# Patterns to strip from free-text description fields
_PRONOUN_RE = re.compile(
    r"\b(he|she|him|her|his|hers|himself|herself|mr\.|ms\.|mrs\.)\b",
    re.IGNORECASE,
)
_NATIONALITY_RE = re.compile(
    r"\b(nationality|citizenship|citizen of|native of|born in)\b[^.;,\n]*",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    """Remove gender pronouns and nationality phrases from free text."""
    text = _PRONOUN_RE.sub("", text)
    text = _NATIONALITY_RE.sub("", text)
    # Collapse multiple spaces
    return re.sub(r"  +", " ", text).strip()


class BiasFilterAgent(BaseAgent):
    name = "BiasFilterAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.current_stage = "filtering"
        logger.info("BiasFilterAgent: anonymizing resume %s (deterministic)", ctx.resume_id)

        if not ctx.parsed_resume:
            ctx.error = "No parsed resume available for bias filtering"
            return ctx

        filtered = copy.deepcopy(ctx.parsed_resume)

        # 1. Anonymize identity fields
        filtered["name"] = "[CANDIDATE_ID]"
        filtered.pop("email", None)
        filtered.pop("phone", None)
        filtered.pop("date_of_birth", None)
        filtered.pop("dob", None)
        filtered.pop("age", None)
        filtered.pop("gender", None)
        filtered.pop("nationality", None)
        filtered.pop("address", None)
        filtered.pop("photo", None)

        # 2. Anonymize institution names in education entries
        for edu in filtered.get("education", []):
            if "institution" in edu:
                edu["institution"] = "[UNIVERSITY]"
            if "school" in edu:
                edu["school"] = "[UNIVERSITY]"

        # 3. Clean free-text descriptions (remove pronouns, nationality signals)
        for exp in filtered.get("experience", []):
            if "description" in exp and isinstance(exp["description"], str):
                exp["description"] = _clean_text(exp["description"])

        if "summary" in filtered and isinstance(filtered["summary"], str):
            filtered["summary"] = _clean_text(filtered["summary"])

        ctx.filtered_resume = filtered
        return ctx
