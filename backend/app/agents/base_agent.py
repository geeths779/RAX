"""Abstract base class for all pipeline agents."""

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING

import google.generativeai as genai

if TYPE_CHECKING:
    from app.agents.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)

_gemini_configured = False


def _ensure_gemini_configured() -> None:
    """Configure the Gemini SDK once, lazily."""
    global _gemini_configured
    if not _gemini_configured:
        from app.config import get_settings
        genai.configure(api_key=get_settings().GOOGLE_API_KEY)
        _gemini_configured = True


class BaseAgent(abc.ABC):
    """Every agent implements `run()` which mutates and returns the PipelineContext."""

    name: str = "BaseAgent"

    # Shared Gemini model instances (lazy-initialised on first use)
    _llm: genai.GenerativeModel | None = None
    _embedding_model_name: str = "models/text-embedding-004"

    @classmethod
    def get_llm(cls) -> genai.GenerativeModel:
        _ensure_gemini_configured()
        if cls._llm is None:
            cls._llm = genai.GenerativeModel("gemini-1.5-pro")
        return cls._llm

    @classmethod
    async def embed_text(cls, text: str) -> list[float]:
        """Generate a 768-dim embedding using Gemini text-embedding-004."""
        _ensure_gemini_configured()
        result = genai.embed_content(
            model=cls._embedding_model_name,
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]

    @abc.abstractmethod
    async def run(self, ctx: "PipelineContext") -> "PipelineContext":
        """Execute this agent's logic and return the updated context."""
        ...

    def __repr__(self) -> str:
        return f"<{self.name}>"
