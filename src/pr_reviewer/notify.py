"""Optional best-effort Slack summary notification (Phase 5).

Posts a short review summary to a Slack incoming webhook when `slack-webhook` is set.
Best-effort by contract: any failure here is logged and swallowed so it can never fail
the user's build or interrupt the review (hard rule 1).
"""
from __future__ import annotations

import logging

import requests

from pr_reviewer.review import SEVERITY_EMOJI

log = logging.getLogger("pr-reviewer")


def _summary_text(event, findings: list) -> str:
    title = f"*AI PR review* — {event.owner}/{event.repo}#{event.number}"
    if not findings:
        return f"{title}\n✅ No findings."
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    breakdown = ", ".join(
        f"{SEVERITY_EMOJI.get(sev, '')} {counts[sev]} {sev}"
        for sev in ("high", "medium", "low")
        if counts.get(sev)
    )
    n = len(findings)
    return f"{title}\n🔎 {n} finding{'s' if n != 1 else ''} ({breakdown})."


def notify_slack(settings, event, findings: list) -> None:
    """Post a short review summary to the configured Slack webhook, if any.

    No-op when `slack-webhook` is unset. Never raises: a notify failure is logged and
    ignored so it cannot fail the user's build.
    """
    webhook = settings.slack_webhook
    if not webhook:
        return
    try:
        resp = requests.post(
            webhook, json={"text": _summary_text(event, findings)}, timeout=15
        )
        resp.raise_for_status()
        log.info("posted review summary to Slack")
    except Exception as exc:  # best-effort: never fail the build on a notify error
        log.warning("slack notify failed (ignored): %s", exc)
