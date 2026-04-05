import os
from functools import lru_cache

import google.generativeai as genai


DEFAULT_TEXT_MODEL = "gemini-2.5-flash"
DEFAULT_EMBEDDING_MODEL = "models/text-embedding-004"


@lru_cache(maxsize=1)
def _configure() -> bool:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    genai.configure(api_key=api_key)
    return True


@lru_cache(maxsize=1)
def get_text_model(model_name: str = DEFAULT_TEXT_MODEL) -> genai.GenerativeModel:
    _configure()
    return genai.GenerativeModel(model_name)


def get_embedding_model_name(model_name: str = DEFAULT_EMBEDDING_MODEL) -> str:
    _configure()
    return model_name
