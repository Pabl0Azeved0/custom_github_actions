from pr_reviewer import main as main_mod
from pr_reviewer.config import Settings
from pr_reviewer.github_api import PullRequestEvent


def test_run_no_event_returns_zero(monkeypatch):
    monkeypatch.setattr(main_mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(main_mod, "load_event", lambda: None)
    assert main_mod.run() == 0


def test_run_swallows_errors(monkeypatch):
    def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(main_mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(main_mod, "load_event", boom)
    assert main_mod.run() == 0


def test_run_fetches_changed_files_once(monkeypatch):
    calls = {"n": 0}

    def counting_fetch(settings, event):
        calls["n"] += 1
        return []

    monkeypatch.setattr(main_mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(main_mod, "load_event", lambda: PullRequestEvent("o", "r", 1))
    monkeypatch.setattr(main_mod, "fetch_changed_files", counting_fetch)
    monkeypatch.setattr(main_mod, "render_diff", lambda files, settings: "")
    monkeypatch.setattr(main_mod, "review_diff", lambda s, d: [])
    monkeypatch.setattr(main_mod, "post_review", lambda s, e, f, files=None: None)
    assert main_mod.run() == 0
    assert calls["n"] == 1
