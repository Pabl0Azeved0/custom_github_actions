"""GitHub API access: read the PR diff (Phase 2) and post review comments (Phase 4).

Scaffold stubs — the real diff collection and Reviews-API posting land in later phases.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class PullRequestEvent:
    owner: str
    repo: str
    number: int


def load_event() -> "PullRequestEvent | None":
    """Parse the pull_request event payload GitHub writes to GITHUB_EVENT_PATH."""
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    pr = payload.get("pull_request")
    repo = payload.get("repository")
    if not pr or not repo:
        return None
    full = repo.get("full_name", "/")
    owner, _, name = full.partition("/")
    return PullRequestEvent(owner=owner, repo=name, number=pr.get("number"))


def collect_diff(settings, event: PullRequestEvent) -> str:
    """Fetch the PR diff, honoring the max-diff budget and exclude patterns. (Phase 2)"""
    # TODO(phase-2): fetch via the GitHub API, filter excluded/generated files, and
    # enforce settings.max_diff_bytes. Returns empty until implemented.
    return ""


def post_review(settings, event: PullRequestEvent, findings: list) -> None:
    """Post a summary + inline comments via the Reviews API, updating on re-push. (Phase 4)"""
    # TODO(phase-4): post via the Reviews API with a stable marker so re-pushes update
    # rather than duplicate; cap at settings.max_findings.
    return None
