from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PullRequestEvent:
    owner: str
    repo: str
    number: int


@dataclass
class ChangedFile:
    path: str
    status: str
    patch: str  # unified diff hunk for this file ("" when GitHub omits it, e.g. binaries)


@dataclass
class Finding:
    path: str
    line: int
    severity: str
    message: str


SEVERITY_EMOJI = {"high": "🔴", "medium": "🟠", "low": "🟡"}
