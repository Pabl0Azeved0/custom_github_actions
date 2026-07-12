from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(Exception):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str: ...


def get_provider(settings) -> LLMProvider:
    name = settings.llm_provider
    if name == "groq":
        from pr_reviewer.llm.groq_provider import GroqProvider

        if not settings.llm_api_key:
            raise LLMError("llm-api-key is required for groq")
        return GroqProvider(settings.llm_api_key, settings.llm_model)
    raise LLMError(f"unknown llm provider: {name}")
