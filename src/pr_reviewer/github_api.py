"""GitHub API access: read the PR diff (Phase 2) and post review comments (Phase 4).

Scaffold stubs — the real diff collection and Reviews-API posting land in later phases.
"""
from __future__ import annotations

import json
import logging
import os
import re

from pr_reviewer.github.client import _API_ROOT, _delete, _paginate, _patch, _post
from pr_reviewer.github.diff import fetch_changed_files
from pr_reviewer.models import PullRequestEvent, SEVERITY_EMOJI

log = logging.getLogger("pr-reviewer")

# Hidden markers let us find our own comments on re-push and update them in place
# instead of piling up duplicates. They render as nothing in the GitHub UI.
_SUMMARY_MARKER = "<!-- pr-reviewer:summary -->"
_INLINE_MARKER = "<!-- pr-reviewer:inline -->"


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
    emoji = SEVERITY_EMOJI.get(f.severity, "")
    where = f"`{f.path}:{f.line}`" if f.line else f"`{f.path}`"
    return f"- {emoji} **{f.severity}** {where} — {f.message}"


def _summary_body(findings: list, unanchored: list, fail_on_findings: bool = False) -> str:
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
    if fail_on_findings:
        lines += ["", "_This review can fail the build when findings are present (fail-on-findings)._"]
    else:
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
    body = _summary_body(findings, unanchored, settings.fail_on_findings)
    existing = _find_comment(settings, event, _SUMMARY_MARKER)
    base = f"{_API_ROOT}/repos/{event.owner}/{event.repo}/issues"
    if existing is not None:
        _patch(settings, f"{base}/comments/{existing}", {"body": body})
    else:
        _post(settings, f"{base}/{event.number}/comments", {"body": body})


def _commentable_map(settings, event: PullRequestEvent, files=None) -> "dict[str, set[int]]":
    """Per-file set of new-file lines the Reviews API will accept an inline comment on."""
    if files is None:
        files = fetch_changed_files(settings, event)
    return {f.path: _commentable_lines(f.patch) for f in files}


def _inline_body(f) -> str:
    emoji = SEVERITY_EMOJI.get(f.severity, "")
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


def post_review(settings, event: PullRequestEvent, findings: list, files=None) -> None:
    """Post/update a summary comment and inline review comments for the findings.

    Idempotent across re-pushes: hidden markers identify our own comments, so the summary
    is edited in place and stale inline comments are replaced instead of duplicated.
    Findings on a diff line become inline comments; the rest are listed in the summary.
    """
    commentable = _commentable_map(settings, event, files)
    anchored, unanchored = _split_findings(findings, commentable)
    _sync_summary(settings, event, findings, unanchored)
    _sync_inline(settings, event, anchored)
