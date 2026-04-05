"""Stage 3b: Embed resume/JD text into 768-dim vectors via Gemini and store in Qdrant."""

from __future__ import annotations

import logging

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

# Qdrant collection names
RESUMES_COLLECTION = "resumes"
JOB_DESCRIPTIONS_COLLECTION = "job_descriptions"
VECTOR_DIM = 768


class EmbeddingAgent(BaseAgent):
    name = "EmbeddingAgent"

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Embed the filtered resume text and upsert into Qdrant resumes collection."""
        ctx.current_stage = "embedding"
        logger.info("EmbeddingAgent: embedding resume %s", ctx.resume_id)

        if not ctx.filtered_resume:
            ctx.error = "No filtered resume available for embedding"
            return ctx

        # TODO Phase 4: Full implementation
        #   1. Build text representation from filtered_resume fields
        #   2. embedding = await self.embed_text(text)
        #   3. qdrant_client.upsert(
        #        collection_name=RESUMES_COLLECTION,
        #        points=[PointStruct(id=ctx.resume_id, vector=embedding, payload={...})]
        #      )

        ctx.qdrant_point_id = ctx.resume_id  # placeholder
        return ctx

    async def embed_job(self, job_id: str, description_text: str) -> str:
        """Embed a job description and store in Qdrant. Returns point_id."""
        logger.info("EmbeddingAgent: embedding job %s", job_id)
        # TODO Phase 4: Full implementation
        #   embedding = await self.embed_text(description_text)
        #   qdrant_client.upsert(collection_name=JOB_DESCRIPTIONS_COLLECTION, ...)
        return job_id  # placeholder
