"""GitHub API access: read the PR diff (Phase 2) and post review comments (Phase 4).

Scaffold stubs — the real diff collection and Reviews-API posting land in later phases.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

import requests

log = logging.getLogger("pr-reviewer")

_API_ROOT = "https://api.github.com"


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


def _glob_to_regex(pattern: str) -> str:
    """Translate a gitignore-style glob into a regex anchored to the whole path.

    `**/` matches zero or more leading directories, `**` matches across separators,
    `*` matches within a single path segment, `?` matches one non-separator char.
    """
    i, n = 0, len(pattern)
    out: list[str] = []
    while i < n:
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "(?s:" + "".join(out) + r")\Z"


def is_excluded(path: str, patterns: list[str]) -> bool:
    return any(re.match(_glob_to_regex(pat), path) for pat in patterns)


def _include(f: ChangedFile, exclude: list[str]) -> bool:
    """Decide whether a changed file should be sent to the reviewer."""
    if not f.patch:  # binary or otherwise no textual diff
        return False
    if f.status == "removed":  # a pure deletion has nothing to review
        return False
    return not is_excluded(f.path, exclude)


def _get(settings, url: str, params: "dict | None" = None) -> requests.Response:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    resp = requests.get(url, headers=headers, params=params, timeout=60)
    resp.raise_for_status()
    return resp


def _paginate(settings, url: str) -> "list[dict]":
    items: list[dict] = []
    page = 1
    while True:
        batch = _get(settings, url, params={"per_page": 100, "page": page}).json()
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def fetch_changed_files(settings, event: PullRequestEvent) -> "list[ChangedFile]":
    url = f"{_API_ROOT}/repos/{event.owner}/{event.repo}/pulls/{event.number}/files"
    return [
        ChangedFile(
            path=f.get("filename", ""),
            status=f.get("status", ""),
            patch=f.get("patch", "") or "",
        )
        for f in _paginate(settings, url)
    ]


def _render(files: "list[ChangedFile]") -> str:
    return "\n\n".join(f"--- {f.path} ({f.status})\n{f.patch}" for f in files)


def _apply_budget(diff: str, max_bytes: int) -> str:
    encoded = diff.encode("utf-8")
    if len(encoded) <= max_bytes:
        return diff
    truncated = encoded[:max_bytes].decode("utf-8", "ignore")
    return truncated + "\n\n[... diff truncated to fit the review budget ...]"


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
