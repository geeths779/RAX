from dataclasses import dataclass
from typing import Any


@dataclass
class PipelineContext:
    resume_id: str
    job_id: str
    raw_text: str | None = None
    parsed_resume: dict[str, Any] | None = None
    filtered_resume: dict[str, Any] | None = None
    resume_embedding: list[float] | None = None
    match_result: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    qdrant_point_id: str | None = None
