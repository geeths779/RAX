"""Abstract base class for all pipeline agents."""

from __future__ import annotations

import abc
import asyncio
import logging
from typing import TYPE_CHECKING

from google import genai
from google.genai import types

if TYPE_CHECKING:
    from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

_genai_client: genai.Client | None = None

# Timeout (seconds) applied to every Gemini API call
GEMINI_TIMEOUT = 90


def _get_genai_client() -> genai.Client:
    """Return the singleton google-genai Client, creating it lazily."""
    global _genai_client
    if _genai_client is None:
        from app.config import get_settings
        _genai_client = genai.Client(api_key=get_settings().GOOGLE_API_KEY)
    return _genai_client


def strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from LLM output."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


class BaseAgent(abc.ABC):
    """Every agent implements `run()` which mutates and returns the PipelineContext."""

    name: str = "BaseAgent"

    _model_name: str = "gemini-2.5-flash"
    _embedding_model_name: str = "gemini-embedding-001"

    @classmethod
    async def call_llm(cls, prompt: str) -> str:
        """Call Gemini with a timeout. Returns stripped text or raises on failure."""
        client = _get_genai_client()
        try:
            async with asyncio.timeout(GEMINI_TIMEOUT):
                response = await client.aio.models.generate_content(
                    model=cls._model_name,
                    contents=prompt,
                )
        except TimeoutError:
            raise RuntimeError(f"Gemini API call timed out after {GEMINI_TIMEOUT}s")

        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned empty response (possibly blocked by safety filters)")
        return strip_markdown_fences(text)

    @classmethod
    async def embed_text(cls, text: str) -> list[float]:
        """Generate a 768-dim embedding using Gemini embedding model."""
        client = _get_genai_client()
        try:
            async with asyncio.timeout(GEMINI_TIMEOUT):
                result = await client.aio.models.embed_content(
                    model=cls._embedding_model_name,
                    contents=text,
                    config=types.EmbedContentConfig(output_dimensionality=768),
                )
        except TimeoutError:
            raise RuntimeError(f"Gemini embed_content timed out after {GEMINI_TIMEOUT}s")
        return result.embeddings[0].values

    @abc.abstractmethod
    async def run(self, ctx: "PipelineContext") -> "PipelineContext":
        """Execute this agent's logic and return the updated context."""
        ...

    def __repr__(self) -> str:
        return f"<{self.name}>"
