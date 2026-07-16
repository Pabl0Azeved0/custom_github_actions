"""Turn a PR diff into a small set of high-confidence findings via the LLM. (Phase 3)"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from pr_reviewer.llm.provider import get_provider

log = logging.getLogger("pr-reviewer")

SEVERITY_EMOJI = {"high": "🔴", "medium": "🟠", "low": "🟡"}

_LENIENT = "Only flag issues you are highly confident are real problems; when in doubt, say nothing."
_BALANCED = "Flag issues you are reasonably confident are real problems."
_STRICT = "Flag anything that could plausibly be a bug, security issue, or obvious simplification, even if you are only moderately confident."

_STRICTNESS_GUIDANCE = {
    "lenient": _LENIENT,
    "low": _LENIENT,
    "balanced": _BALANCED,
    "strict": _STRICT,
    "high": _STRICT,
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


def parse_findings(raw: str) -> "list[Finding]":
    """Parse the LLM's raw response into Finding objects, tolerating malformed output."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()

    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        log.warning("failed to parse LLM findings as JSON")
        return []

    if isinstance(data, dict):
        data = data.get("findings", [])
    if not isinstance(data, list):
        return []

    findings: list[Finding] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        message = item.get("message")
        if not path or not message:
            continue
        try:
            line = int(item.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        severity = str(item.get("severity", "")).lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        findings.append(Finding(path=path, line=line, severity=severity, message=message))
    return findings


def review_diff(settings, diff: str) -> "list[Finding]":
    """Send the diff to the LLM and parse findings, capped at settings.max_findings."""
    if not diff.strip():
        return []
    raw = get_provider(settings).generate(build_prompt(settings, diff))
    findings = parse_findings(raw)
    return findings[: settings.max_findings]
