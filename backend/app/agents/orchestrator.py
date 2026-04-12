"""Pipeline Orchestrator: wires all agents in sequence with status tracking."""

from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any, Callable, Coroutine

from neo4j import AsyncDriver
from qdrant_client import QdrantClient

from app.agents.pipeline_context import PipelineContext
from app.agents.resume_parser_agent import ResumeParserAgent
from app.agents.experience_extractor import ExperienceExtractorAgent
from app.agents.bias_filter_agent import BiasFilterAgent
from app.agents.graph_ingestion_agent import GraphIngestionAgent
from app.agents.embedding_agent import EmbeddingAgent
from app.agents.hybrid_matching_agent import HybridMatchingAgent
from app.agents.scoring_agent import ScoringAgent

logger = logging.getLogger(__name__)

# Type alias for the status callback (WebSocket publisher)
StatusCallback = Callable[[str, str, str], Coroutine[Any, Any, None]]
# signature: async callback(resume_id: str, stage: str, status: str)


class PipelineOrchestrator:
    """Runs the full agent pipeline for a single resume against a job.

    Usage:
        orchestrator = PipelineOrchestrator(on_status_change=ws_publish)
        ctx = await orchestrator.run(resume_id="...", job_id="...", raw_text="...")
    """

    def __init__(
        self,
        on_status_change: StatusCallback | None = None,
        neo4j_driver: AsyncDriver | None = None,
        qdrant_client: QdrantClient | None = None,
    ):
        self._on_status = on_status_change
        self._parser = ResumeParserAgent()
        self._experience_extractor = ExperienceExtractorAgent()
        self._bias_filter = BiasFilterAgent()
        self._graph_ingestion = GraphIngestionAgent(driver=neo4j_driver)
        self._embedding = EmbeddingAgent(qdrant_client=qdrant_client)
        self._hybrid_matching = HybridMatchingAgent(
            neo4j_driver=neo4j_driver,
            qdrant_client=qdrant_client,
        )
        self._scoring = ScoringAgent()

    async def _notify(self, resume_id: str, stage: str, status: str) -> None:
        """Push status update via callback (WebSocket) if registered."""
        if self._on_status:
            try:
                await self._on_status(resume_id, stage, status)
            except Exception:
                logger.warning("Status callback failed for %s/%s", resume_id, stage)

    async def run(
        self,
        resume_id: str,
        job_id: str,
        raw_text: str = "",
        file_bytes: bytes = b"",
        filename: str = "",
    ) -> PipelineContext:
        """Execute the optimized pipeline:
        Parse → Bias Filter (instant) → [ExpExtract ║ Graph ║ Embed] → Match → Score.
        """

        ctx = PipelineContext(
            resume_id=resume_id,
            job_id=job_id,
            raw_text=raw_text,
            file_bytes=file_bytes,
            filename=filename,
        )

        # Load job data so scoring has full context
        try:
            from app.db.session import async_session_factory
            from app.models.job import Job
            from sqlalchemy import select
            import uuid

            async with async_session_factory() as db:
                result = await db.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
                job = result.scalar_one_or_none()
                if job:
                    ctx.job_title = job.title or ""
                    ctx.job_description = job.description or ""
                    ctx.job_requirements = job.requirements_raw or {}
        except Exception as exc:
            logger.warning("Failed to load job data for %s: %s", job_id, exc)

        # Stage 1: Parse
        await self._notify(resume_id, "parsing", "in_progress")
        ctx = await self._parser.run(ctx)
        if ctx.error:
            await self._notify(resume_id, "parsing", "failed")
            return ctx
        await self._notify(resume_id, "parsing", "complete")

        # Stage 2: Bias Filter (deterministic — instant, no LLM call)
        await self._notify(resume_id, "filtering", "in_progress")
        ctx = await self._bias_filter.run(ctx)
        if ctx.error:
            await self._notify(resume_id, "filtering", "failed")
            return ctx
        await self._notify(resume_id, "filtering", "complete")

        # Stage 3: Experience Extract ║ Graph Ingestion ║ Embedding (all in parallel)
        # Experience extract: LLM call using raw_text (independent of filtered_resume)
        # Graph ingestion: writes to Neo4j from parsed_resume
        # Embedding: generates vector from filtered_resume
        # All three are independent — run concurrently for maximum speed.
        await self._notify(resume_id, "graph_ingestion", "in_progress")
        await self._notify(resume_id, "embedding", "in_progress")

        graph_ctx = copy.copy(ctx)
        embed_ctx = copy.copy(ctx)
        exp_ctx = copy.copy(ctx)

        graph_task = asyncio.create_task(self._graph_ingestion.run(graph_ctx))
        embed_task = asyncio.create_task(self._embedding.run(embed_ctx))
        exp_task = asyncio.create_task(self._experience_extractor.run(exp_ctx))

        results = await asyncio.gather(graph_task, embed_task, exp_task, return_exceptions=True)

        # Merge Graph result
        if isinstance(results[0], BaseException):
            logger.warning("Graph ingestion crashed: %s", results[0])
            await self._notify(resume_id, "graph_ingestion", "failed")
        else:
            graph_ctx = results[0]
            ctx.graph_node_id = graph_ctx.graph_node_id
            if graph_ctx.error:
                logger.warning("GraphIngestionAgent error (non-fatal): %s", graph_ctx.error)
                await self._notify(resume_id, "graph_ingestion", "failed")
            else:
                await self._notify(resume_id, "graph_ingestion", "complete")

        # Merge Embedding result
        if isinstance(results[1], BaseException):
            logger.warning("Embedding crashed: %s", results[1])
            await self._notify(resume_id, "embedding", "failed")
        else:
            embed_ctx = results[1]
            ctx.qdrant_point_id = embed_ctx.qdrant_point_id
            if embed_ctx.error:
                logger.warning("EmbeddingAgent error (non-fatal): %s", embed_ctx.error)
                await self._notify(resume_id, "embedding", "failed")
            else:
                await self._notify(resume_id, "embedding", "complete")

        # Merge Experience Extraction result (non-fatal)
        if isinstance(results[2], BaseException):
            logger.warning("ExperienceExtractor crashed (non-fatal): %s", results[2])
        else:
            exp_ctx = results[2]
            if exp_ctx.enriched_experience:
                ctx.enriched_experience = exp_ctx.enriched_experience
                logger.info("ExperienceExtractor: total_years=%.1f seniority=%s",
                            ctx.enriched_experience.get("total_years_experience", 0),
                            ctx.enriched_experience.get("seniority_level", "unknown"))

        # Stage 4: Hybrid Matching (best-effort — skip if graph/vector data is missing)
        await self._notify(resume_id, "hybrid_matching", "in_progress")
        ctx = await self._hybrid_matching.run(ctx)
        if ctx.error:
            logger.warning("HybridMatchingAgent error (non-fatal): %s", ctx.error)
            await self._notify(resume_id, "hybrid_matching", "failed")
            ctx.error = ""  # Clear so scoring can still proceed
        else:
            await self._notify(resume_id, "hybrid_matching", "complete")

        # Stage 5: Scoring
        await self._notify(resume_id, "scoring", "in_progress")
        ctx = await self._scoring.run(ctx)
        if ctx.error:
            await self._notify(resume_id, "scoring", "failed")
            return ctx
        await self._notify(resume_id, "scoring", "complete")

        ctx.current_stage = "completed"
        await self._notify(resume_id, "completed", "complete")

        logger.info("Pipeline complete for resume %s — score: %s",
                     resume_id, ctx.analysis.get("overall_score", "N/A"))
        return ctx
