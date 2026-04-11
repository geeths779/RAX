"""Stage 3b: Embed resume/JD text into 768-dim vectors via Gemini and store in Qdrant."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.agents.base_agent import BaseAgent
from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

# Qdrant collection names
RESUMES_COLLECTION = "resumes"
JOB_DESCRIPTIONS_COLLECTION = "job_descriptions"
VECTOR_DIM = 768


def _build_resume_text(resume: dict[str, Any]) -> str:
    """Concatenate filtered resume fields into a single string for embedding."""
    parts: list[str] = []

    for skill in resume.get("skills", []):
        name = skill.get("name", "")
        years = skill.get("years", 0)
        prof = skill.get("proficiency", "")
        parts.append(f"{name} ({years} years, {prof})")

    for exp in resume.get("experience", []):
        title = exp.get("title", "")
        company = exp.get("company", "")
        desc = exp.get("description", "")
        parts.append(f"{title} at {company}: {desc}")

    for edu in resume.get("education", []):
        degree = edu.get("degree", "")
        field = edu.get("field", "")
        parts.append(f"{degree} in {field}")

    return ". ".join(parts)


def _resume_id_to_uuid(resume_id: str) -> str:
    """Convert a resume_id string to a deterministic UUID for Qdrant point ID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"resume:{resume_id}"))


def _job_id_to_uuid(job_id: str) -> str:
    """Convert a job_id string to a deterministic UUID for Qdrant point ID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"job:{job_id}"))


class EmbeddingAgent(BaseAgent):
    name = "EmbeddingAgent"

    def __init__(self, qdrant_client: QdrantClient | None = None):
        self._client = qdrant_client

    def _ensure_collection(self, collection_name: str) -> None:
        """Create the Qdrant collection if it doesn't exist (sync — call via to_thread)."""
        try:
            if not self._client.collection_exists(collection_name):
                self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
                )
                logger.info("EmbeddingAgent: created collection '%s'", collection_name)
        except Exception:
            # Race condition: another worker may have created it between check and create
            if self._client.collection_exists(collection_name):
                pass
            else:
                raise

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Embed the filtered resume text and upsert into Qdrant resumes collection."""
        ctx.current_stage = "embedding"
        logger.info("EmbeddingAgent: embedding resume %s", ctx.resume_id)

        if not ctx.filtered_resume:
            ctx.error = "No filtered resume available for embedding"
            return ctx

        if not self._client:
            logger.warning("EmbeddingAgent: Qdrant not configured — skipping vector storage")
            # Still generate embedding ID so pipeline can continue
            ctx.qdrant_point_id = _resume_id_to_uuid(ctx.resume_id)
            return ctx

        try:
            text = _build_resume_text(ctx.filtered_resume)
            if not text.strip():
                ctx.error = "Empty resume text — nothing to embed"
                return ctx

            embedding = await self.embed_text(text)

            await asyncio.to_thread(self._ensure_collection, RESUMES_COLLECTION)

            point_id = _resume_id_to_uuid(ctx.resume_id)

            # Build rich payload so semantic queries return useful context
            skills_list = [
                {"name": s.get("name", ""), "years": s.get("years", 0), "proficiency": s.get("proficiency", "")}
                for s in ctx.filtered_resume.get("skills", [])
            ]
            experience_list = [
                {"title": e.get("title", ""), "company": e.get("company", ""), "duration": e.get("duration", ""), "description": e.get("description", "")}
                for e in ctx.filtered_resume.get("experience", [])
            ]
            education_list = [
                {"degree": e.get("degree", ""), "field": e.get("field", ""), "institution": e.get("institution", ""), "year": e.get("year", "")}
                for e in ctx.filtered_resume.get("education", [])
            ]

            payload = {
                "resume_id": ctx.resume_id,
                "job_id": ctx.job_id,
                "resume_text": text,
                "skills": skills_list,
                "skill_names": [s.get("name", "") for s in ctx.filtered_resume.get("skills", [])],
                "experience": experience_list,
                "education": education_list,
            }

            await asyncio.to_thread(
                self._client.upsert,
                collection_name=RESUMES_COLLECTION,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload,
                    )
                ],
            )

            ctx.qdrant_point_id = point_id
            logger.info(
                "EmbeddingAgent: upserted resume %s as point %s (%d dims)",
                ctx.resume_id, point_id, len(embedding),
            )
        except Exception as exc:
            logger.error("EmbeddingAgent: embedding failed: %s", exc)
            ctx.error = f"Embedding failed: {exc}"

        return ctx

    async def embed_job(self, job_id: str, description_text: str, title: str = "", requirements: dict | None = None) -> str:
        """Embed a job description and store in Qdrant. Returns point_id."""
        logger.info("EmbeddingAgent: embedding job %s", job_id)

        if not self._client:
            raise RuntimeError("Qdrant client not configured")

        embedding = await self.embed_text(description_text)

        await asyncio.to_thread(self._ensure_collection, JOB_DESCRIPTIONS_COLLECTION)

        point_id = _job_id_to_uuid(job_id)

        req_skills = []
        if requirements:
            req_skills = requirements.get("skills", [])

        await asyncio.to_thread(
            self._client.upsert,
            collection_name=JOB_DESCRIPTIONS_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "job_id": job_id,
                        "title": title,
                        "description": description_text,
                        "required_skills": req_skills,
                    },
                )
            ],
        )

        logger.info("EmbeddingAgent: upserted job %s as point %s", job_id, point_id)
        return point_id
