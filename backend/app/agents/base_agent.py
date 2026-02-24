from abc import ABC, abstractmethod

from .gemini_client import get_text_model
from .pipeline_context import PipelineContext


class BaseAgent(ABC):
    def __init__(self, model_name: str = "gemini-1.5-pro") -> None:
        self.model_name = model_name
        self.model = get_text_model(model_name)

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError
