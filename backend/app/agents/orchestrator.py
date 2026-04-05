"""Pipeline Orchestrator: wires all agents in sequence with status tracking."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from neo4j import AsyncDriver

from app.agents.pipeline_context import PipelineContext
from app.agents.resume_parser_agent import ResumeParserAgent
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
    ):
        self._on_status = on_status_change
        self._parser = ResumeParserAgent()
        self._bias_filter = BiasFilterAgent()
        self._graph_ingestion = GraphIngestionAgent(driver=neo4j_driver)
        self._embedding = EmbeddingAgent()
        self._hybrid_matching = HybridMatchingAgent()
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
        """Execute the full pipeline: Parse → Filter → [Graph ║ Embed] → Match → Score."""

        ctx = PipelineContext(
            resume_id=resume_id,
            job_id=job_id,
            raw_text=raw_text,
            file_bytes=file_bytes,
            filename=filename,
        )

        # Stage 1: Parse
        await self._notify(resume_id, "parsing", "in_progress")
        ctx = await self._parser.run(ctx)
        if ctx.error:
            await self._notify(resume_id, "parsing", "failed")
            return ctx
        await self._notify(resume_id, "parsing", "complete")

        # Stage 2: Bias Filter
        await self._notify(resume_id, "filtering", "in_progress")
        ctx = await self._bias_filter.run(ctx)
        if ctx.error:
            await self._notify(resume_id, "filtering", "failed")
            return ctx
        await self._notify(resume_id, "filtering", "complete")

        # Stage 3a + 3b: Graph Ingestion ║ Embedding (parallel)
        await self._notify(resume_id, "graph_ingestion", "in_progress")
        await self._notify(resume_id, "embedding", "in_progress")

        graph_task = asyncio.create_task(self._graph_ingestion.run(ctx))
        embed_task = asyncio.create_task(self._embedding.run(ctx))

        graph_ctx, embed_ctx = await asyncio.gather(graph_task, embed_task)

        # Merge parallel results back into a single context
        ctx.graph_node_id = graph_ctx.graph_node_id
        ctx.qdrant_point_id = embed_ctx.qdrant_point_id

        if graph_ctx.error:
            ctx.error = graph_ctx.error
            await self._notify(resume_id, "graph_ingestion", "failed")
            return ctx
        await self._notify(resume_id, "graph_ingestion", "complete")

        if embed_ctx.error:
            ctx.error = embed_ctx.error
            await self._notify(resume_id, "embedding", "failed")
            return ctx
        await self._notify(resume_id, "embedding", "complete")

        # Stage 4: Hybrid Matching
        await self._notify(resume_id, "hybrid_matching", "in_progress")
        ctx = await self._hybrid_matching.run(ctx)
        if ctx.error:
            await self._notify(resume_id, "hybrid_matching", "failed")
            return ctx
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
