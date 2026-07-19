from pr_reviewer import notify
from pr_reviewer.config import Settings
from pr_reviewer.models import Finding, PullRequestEvent


class _FakeResp:
    def raise_for_status(self):
        pass


def test_no_webhook_is_noop(monkeypatch):
    def fake_post(*a, **k):
        raise AssertionError("should not post")

    monkeypatch.setattr(notify.requests, "post", fake_post)
    notify.notify_slack(Settings(), PullRequestEvent("o", "r", 1), [])


def test_posts_summary_when_set(monkeypatch):
    settings = Settings()
    settings.slack_webhook = "https://hooks.slack.com/services/T000/B000/XXXX"
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    findings = [Finding("a.py", 1, "high", "bug")]
    notify.notify_slack(settings, PullRequestEvent("o", "r", 7), findings)
    assert captured["url"] == settings.slack_webhook
    assert "o/r#7" in captured["json"]["text"]
    assert "1 high" in captured["json"]["text"]


def test_swallows_post_errors(monkeypatch):
    settings = Settings()
    settings.slack_webhook = "https://hooks.slack.com/services/T000/B000/XXXX"

    def fake_post(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(notify.requests, "post", fake_post)
    notify.notify_slack(settings, PullRequestEvent("o", "r", 7), [])


def test_rejects_non_slack_webhook(monkeypatch):
    settings = Settings()
    settings.slack_webhook = "http://attacker.example/exfil"

    def fake_post(*a, **k):
        raise AssertionError("should not post to a non-Slack host")

    monkeypatch.setattr(notify.requests, "post", fake_post)
    notify.notify_slack(settings, PullRequestEvent("o", "r", 1), [])


def test_rejects_plaintext_webhook(monkeypatch):
    settings = Settings()
    settings.slack_webhook = "http://hooks.slack.com/services/T000/B000/XXXX"

    def fake_post(*a, **k):
        raise AssertionError("should not post over plaintext http")

    monkeypatch.setattr(notify.requests, "post", fake_post)
    notify.notify_slack(settings, PullRequestEvent("o", "r", 1), [])


def test_summary_text_no_findings():
    text = notify._summary_text(PullRequestEvent("o", "r", 1), [])
    assert "No findings" in text


def test_summary_text_counts():
    findings = [
        Finding("a.py", 1, "high", "bug1"),
        Finding("a.py", 2, "high", "bug2"),
        Finding("a.py", 3, "low", "nit"),
    ]
    text = notify._summary_text(PullRequestEvent("o", "r", 1), findings)
    assert "2 high" in text
    assert "1 low" in text
