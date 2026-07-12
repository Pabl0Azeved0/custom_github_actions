from pr_reviewer import main as main_mod
from pr_reviewer.config import Settings


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
