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

# Hidden markers let us find our own comments on re-push and update them in place
# instead of piling up duplicates. They render as nothing in the GitHub UI.
_SUMMARY_MARKER = "<!-- pr-reviewer:summary -->"
_INLINE_MARKER = "<!-- pr-reviewer:inline -->"

_SEVERITY_EMOJI = {"high": "🔴", "medium": "🟠", "low": "🟡"}


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


def _headers(settings) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _get(settings, url: str, params: "dict | None" = None) -> requests.Response:
    resp = requests.get(url, headers=_headers(settings), params=params, timeout=60)
    resp.raise_for_status()
    return resp


def _post(settings, url: str, payload: dict) -> requests.Response:
    resp = requests.post(url, headers=_headers(settings), json=payload, timeout=60)
    resp.raise_for_status()
    return resp


def _patch(settings, url: str, payload: dict) -> requests.Response:
    resp = requests.patch(url, headers=_headers(settings), json=payload, timeout=60)
    resp.raise_for_status()
    return resp


def _delete(settings, url: str) -> requests.Response:
    resp = requests.delete(url, headers=_headers(settings), timeout=60)
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
    """Fetch the PR diff, drop excluded/binary/deleted files, and enforce the byte budget."""
    files = fetch_changed_files(settings, event)
    included = [f for f in files if _include(f, settings.exclude)]
    diff = _render(included)
    budgeted = _apply_budget(diff, settings.max_diff_bytes)
    truncated = len(budgeted) != len(diff)
    log.info(
        "diff: %d/%d file(s) included, %d bytes%s",
        len(included),
        len(files),
        len(budgeted.encode("utf-8")),
        " (truncated)" if truncated else "",
    )
    return budgeted


def _commentable_lines(patch: str) -> "set[int]":
    """New-file line numbers the Reviews API will accept an inline comment on.

    The Reviews API rejects the whole review if any comment points at a line outside the
    diff, so we only anchor to lines present in a hunk: added (`+`) and context lines on
    the right side. Deleted (`-`) lines don't advance the new-file counter.
    """
    lines: "set[int]" = set()
    new_ln = 0
    for row in patch.splitlines():
        if row.startswith("@@"):
            m = re.search(r"\+(\d+)", row)
            new_ln = int(m.group(1)) if m else 0
        elif row.startswith("+"):
            lines.add(new_ln)
            new_ln += 1
        elif row.startswith("-") or row.startswith("\\"):
            continue
        else:  # context line — present in the new file, so commentable
            lines.add(new_ln)
            new_ln += 1
    return lines


def _split_findings(findings: list, commentable: "dict[str, set[int]]") -> tuple:
    """Partition findings into those anchorable to a diff line and those that aren't."""
    anchored, unanchored = [], []
    for f in findings:
        if f.line and f.line in commentable.get(f.path, set()):
            anchored.append(f)
        else:
            unanchored.append(f)
    return anchored, unanchored


def _finding_line(f) -> str:
    emoji = _SEVERITY_EMOJI.get(f.severity, "")
    where = f"`{f.path}:{f.line}`" if f.line else f"`{f.path}`"
    return f"- {emoji} **{f.severity}** {where} — {f.message}"


def _summary_body(findings: list, unanchored: list) -> str:
    """Build the summary comment. Anchored findings show inline; unanchored list here."""
    lines = [_SUMMARY_MARKER, "## 🤖 AI code review", ""]
    if not findings:
        lines.append("No findings — nothing stood out. 🎉")
    else:
        n = len(findings)
        lines.append(f"Found **{n}** potential issue{'s' if n != 1 else ''}.")
        if unanchored:
            lines += ["", "Not tied to a specific diff line:", ""]
            lines += [_finding_line(f) for f in unanchored]
    lines += ["", "_Report-only — this review never fails your build._"]
    return "\n".join(lines)


def _find_comment(settings, event: PullRequestEvent, marker: str) -> "int | None":
    """Return the id of our previous summary comment (by hidden marker), if any."""
    url = f"{_API_ROOT}/repos/{event.owner}/{event.repo}/issues/{event.number}/comments"
    for c in _paginate(settings, url):
        if marker in (c.get("body") or ""):
            return c.get("id")
    return None


def _sync_summary(settings, event: PullRequestEvent, findings: list, unanchored: list) -> None:
    body = _summary_body(findings, unanchored)
    existing = _find_comment(settings, event, _SUMMARY_MARKER)
    base = f"{_API_ROOT}/repos/{event.owner}/{event.repo}/issues"
    if existing is not None:
        _patch(settings, f"{base}/comments/{existing}", {"body": body})
    else:
        _post(settings, f"{base}/{event.number}/comments", {"body": body})


def _commentable_map(settings, event: PullRequestEvent) -> "dict[str, set[int]]":
    """Per-file set of new-file lines the Reviews API will accept an inline comment on."""
    return {f.path: _commentable_lines(f.patch) for f in fetch_changed_files(settings, event)}


def _inline_body(f) -> str:
    emoji = _SEVERITY_EMOJI.get(f.severity, "")
    return f"{emoji} **{f.severity}** — {f.message}\n\n{_INLINE_MARKER}"


def _delete_stale_inline(settings, event: PullRequestEvent) -> None:
    """Remove our previous run's inline comments (found by marker) so re-pushes replace them."""
    base = f"{_API_ROOT}/repos/{event.owner}/{event.repo}/pulls"
    for c in _paginate(settings, f"{base}/{event.number}/comments"):
        if _INLINE_MARKER in (c.get("body") or ""):
            _delete(settings, f"{base}/comments/{c['id']}")


def _sync_inline(settings, event: PullRequestEvent, anchored: list) -> None:
    _delete_stale_inline(settings, event)
    if not anchored:
        return
    comments = [
        {"path": f.path, "line": f.line, "side": "RIGHT", "body": _inline_body(f)}
        for f in anchored
    ]
    url = f"{_API_ROOT}/repos/{event.owner}/{event.repo}/pulls/{event.number}/reviews"
    # COMMENT requires a body; the invisible marker keeps the review summary blank in the UI.
    _post(settings, url, {"event": "COMMENT", "body": _INLINE_MARKER, "comments": comments})


def post_review(settings, event: PullRequestEvent, findings: list) -> None:
    """Post a summary + inline comments via the Reviews API, updating on re-push. (Phase 4)"""
    # TODO(phase-4): post via the Reviews API with a stable marker so re-pushes update
    # rather than duplicate; cap at settings.max_findings.
    return None
