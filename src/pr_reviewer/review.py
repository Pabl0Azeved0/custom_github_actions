"""Turn a PR diff into a small set of high-confidence findings via the LLM. (Phase 3)"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Finding:
    path: str
    line: int
    severity: str
    message: str


def review_diff(settings, diff: str) -> "list[Finding]":
    """Send the diff to the LLM and parse findings. (Phase 3)

    Scaffold stub: returns no findings until the prompt + parser land.
    """
    # TODO(phase-3): build the focused review prompt (correctness, security, obvious
    # simplifications; explicitly no style nitpicks), call get_provider(settings).generate,
    # parse JSON findings, cap at settings.max_findings.
    return []
