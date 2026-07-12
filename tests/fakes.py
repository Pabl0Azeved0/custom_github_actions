"""Offline fakes for exercising the reviewer without a network or a live LLM.

`ScriptedLLM` implements the LLMProvider interface and returns a canned response, so the
review logic and parsing can be tested deterministically. Expanded with golden diffs in
Phase 6.
"""
from __future__ import annotations

from pr_reviewer.llm.provider import LLMProvider


class ScriptedLLM(LLMProvider):
    def __init__(self, response: str = "[]") -> None:
        self._response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._response
