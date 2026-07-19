from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv


def _local_run() -> bool:
    """True only for explicit local runs. Never true in the Action.

    A Docker action's working directory is the checked-out PR, so reading a .env (or bare
    env names) there would let a PR author override our inputs. Opt in explicitly instead.
    """
    return os.getenv("PR_REVIEWER_LOCAL") == "1"


if _local_run():
    load_dotenv()


def _input(name: str, default: str = "") -> str:
    """Read a GitHub Action input.

    GitHub passes `with:` inputs as `INPUT_<UPPER-NAME>` env vars (hyphens kept). For
    explicit local runs (PR_REVIEWER_LOCAL=1) we also accept the bare, underscored name
    (e.g. LLM_PROVIDER) as a fallback.
    """
    upper = name.upper()
    env_input = os.getenv(f"INPUT_{upper}")
    if env_input:
        return env_input
    if _local_run():
        bare = os.getenv(upper.replace("-", "_"))
        if bare:
            return bare
    return default


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_patterns(value: str) -> list[str]:
    # Split on newlines and commas; drop blanks/whitespace.
    parts = value.replace(",", "\n").splitlines()
    return [p.strip() for p in parts if p.strip()]


@dataclass
class Settings:
    # LLM (pluggable — mirrors master-profile's provider pattern).
    llm_provider: str = field(default_factory=lambda: _input("llm-provider", "groq"))
    llm_model: str = field(
        default_factory=lambda: _input("llm-model", "llama-3.3-70b-versatile")
    )
    llm_api_key: str | None = field(default_factory=lambda: _input("llm-api-key") or None)

    # GitHub.
    github_token: str | None = field(default_factory=lambda: _input("github-token") or None)

    # Review tuning.
    strictness: str = field(default_factory=lambda: _input("strictness", "balanced"))
    max_findings: int = field(
        default_factory=lambda: _as_int(_input("max-findings", "10"), 10)
    )
    max_diff_bytes: int = field(
        default_factory=lambda: _as_int(_input("max-diff-bytes", "60000"), 60000)
    )
    exclude: list[str] = field(default_factory=lambda: _as_patterns(_input("exclude", "")))
    fail_on_findings: bool = field(
        default_factory=lambda: _as_bool(_input("fail-on-findings", "false"))
    )
    slack_webhook: str | None = field(default_factory=lambda: _input("slack-webhook") or None)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
