from __future__ import annotations

import requests

from pr_reviewer.llm.provider import LLMError, LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, prompt: str) -> str:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    # An injected diff can ask for an endless answer; max-findings JSON
                    # needs far less than this, so cap what we pay for and parse.
                    "max_tokens": 2048,
                },
                timeout=120,
            )
        except requests.RequestException as exc:
            raise LLMError(str(exc)) from exc
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise LLMError(str(exc)) from exc
        return resp.json()["choices"][0]["message"]["content"]
