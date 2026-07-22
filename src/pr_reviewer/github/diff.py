from __future__ import annotations

import logging
import re
from functools import lru_cache

from pr_reviewer.github.client import _API_ROOT, _paginate
from pr_reviewer.models import ChangedFile, PullRequestEvent

log = logging.getLogger("pr-reviewer")


@lru_cache(maxsize=None)
def _glob_to_regex(pattern: str) -> "re.Pattern[str]":
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
    return re.compile("(?s:" + "".join(out) + r")\Z")


# A glob like `**/*a*a*a*b` compiles to nested unbounded quantifiers, which backtrack
# super-linearly in the length of the path being matched. The path comes from the PR
# author, so bound it: real repo paths are far shorter than this.
_MAX_MATCH_PATH = 512


def is_excluded(path: str, patterns: list[str]) -> bool:
    if len(path) > _MAX_MATCH_PATH:
        log.warning("path over %d chars not matched against exclude patterns", _MAX_MATCH_PATH)
        return False
    return any(_glob_to_regex(pat).match(path) for pat in patterns)


def _include(f: ChangedFile, exclude: list[str]) -> bool:
    """Decide whether a changed file should be sent to the reviewer."""
    if not f.patch:  # binary or otherwise no textual diff
        return False
    if f.status == "removed":  # a pure deletion has nothing to review
        return False
    return not is_excluded(f.path, exclude)


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


def _render(files: "list[ChangedFile]", max_bytes: "int | None" = None) -> str:
    chunks: list[str] = []
    size = 0
    for f in files:
        chunks.append(f"--- {f.path} ({f.status})\n{f.patch}")
        if max_bytes is None:
            continue
        size += len(chunks[-1].encode("utf-8")) + (2 if len(chunks) > 1 else 0)
        if size > max_bytes:
            break
    return "\n\n".join(chunks)


def _apply_budget(diff: str, max_bytes: int) -> str:
    encoded = diff.encode("utf-8")
    if len(encoded) <= max_bytes:
        return diff
    truncated = encoded[:max_bytes].decode("utf-8", "ignore")
    return truncated + "\n\n[... diff truncated to fit the review budget ...]"


def render_diff(files: "list[ChangedFile]", settings) -> str:
    """Filter fetched files (excluded/binary/deleted) and enforce the byte budget."""
    included = [f for f in files if _include(f, settings.exclude)]
    diff = _render(included, settings.max_diff_bytes)
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


def collect_diff(settings, event: PullRequestEvent) -> str:
    """Fetch the PR diff, drop excluded/binary/deleted files, and enforce the byte budget."""
    return render_diff(fetch_changed_files(settings, event), settings)
