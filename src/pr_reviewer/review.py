"""Turn a PR diff into a small set of high-confidence findings via the LLM. (Phase 3)"""
from __future__ import annotations

from dataclasses import dataclass

_STRICTNESS_GUIDANCE = {
    "lenient": "Only flag issues you are highly confident are real problems; when in doubt, say nothing.",
    "balanced": "Flag issues you are reasonably confident are real problems.",
    "strict": "Flag anything that could plausibly be a bug, security issue, or obvious simplification, even if you are only moderately confident.",
}


@dataclass
class Finding:
    path: str
    line: int
    severity: str
    message: str


def build_prompt(settings, diff: str) -> str:
    """Build the focused code-review prompt sent to the LLM."""
    guidance = _STRICTNESS_GUIDANCE.get(settings.strictness, _STRICTNESS_GUIDANCE["balanced"])
    return f"""You are a senior code reviewer examining a pull request diff.

Report ONLY correctness bugs, security issues, and obvious simplifications (clearly
redundant or dead code). Do NOT report style, formatting, naming, or subjective
preferences.

Prefer a few high-confidence findings over many uncertain ones. {guidance}

Return ONLY a JSON array (no prose, no markdown fence). Each element must be an object
with keys:
- path (string): the file path from the diff
- line (int): the line number in the new file
- severity (string): one of "high", "medium", "low"
- message (string): one concise sentence

Return [] if there is nothing to report. Report at most {settings.max_findings} findings.

Diff:
{diff}"""


def review_diff(settings, diff: str) -> "list[Finding]":
    """Send the diff to the LLM and parse findings. (Phase 3)

    Scaffold stub: returns no findings until the parser + provider wiring land.
    """
    # TODO(phase-3): call get_provider(settings).generate(build_prompt(...)), parse JSON
    # findings, cap at settings.max_findings.
    return []
