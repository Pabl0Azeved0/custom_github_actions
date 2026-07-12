"""Entry point for the AI PR reviewer Action.

Orchestrates: load event -> collect diff -> LLM review -> post comments. Honors the hard
rule that a provider/LLM failure never fails the user's build (report-only unless
fail-on-findings is set).
"""
from __future__ import annotations

import logging
import sys

from pr_reviewer.config import get_settings
from pr_reviewer.github_api import collect_diff, load_event, post_review
from pr_reviewer.review import review_diff

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("pr-reviewer")


def run() -> int:
    settings = get_settings()
    findings: list = []
    try:
        event = load_event()
        if event is None:
            log.info("no pull_request event found; nothing to review")
            return 0
        log.info("reviewing %s/%s#%s", event.owner, event.repo, event.number)
        diff = collect_diff(settings, event)
        findings = review_diff(settings, diff)
        post_review(settings, event, findings)
        log.info("review complete: %d finding(s)", len(findings))
    except Exception as exc:  # hard rule: never fail the build on our own error
        log.warning("pr-reviewer degraded, skipping review: %s", exc)
        return 0
    if settings.fail_on_findings and findings:
        return 1
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
