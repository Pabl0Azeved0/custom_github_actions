import time

from pr_reviewer.config import Settings
from pr_reviewer.github import client, diff
from pr_reviewer.models import ChangedFile, PullRequestEvent


def test_is_excluded_lock_and_dist():
    pats = ["**/*.lock", "**/dist/**"]
    assert diff.is_excluded("poetry.lock", pats)
    assert diff.is_excluded("a/b/poetry.lock", pats)
    assert diff.is_excluded("dist/app.js", pats)
    assert diff.is_excluded("web/dist/app.js", pats)


def test_is_excluded_negatives():
    pats = ["**/*.lock", "**/dist/**"]
    assert not diff.is_excluded("src/app.py", pats)
    assert not diff.is_excluded("locket.py", pats)


def test_include_decision():
    ex = ["**/*.lock"]
    assert diff._include(ChangedFile("src/a.py", "modified", "@@ -1 +1 @@\n-x\n+y"), ex)
    assert not diff._include(ChangedFile("img.png", "added", ""), ex)
    assert not diff._include(ChangedFile("src/a.py", "removed", "@@"), ex)
    assert not diff._include(ChangedFile("poetry.lock", "modified", "@@"), ex)


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


def test_fetch_changed_files(monkeypatch):
    def fake_get(settings, url, params=None):
        if params["page"] == 1:
            return _FakeResp([{"filename": "a.py", "status": "modified", "patch": "@@"}])
        return _FakeResp([])

    monkeypatch.setattr(client, "_get", fake_get)
    files = diff.fetch_changed_files(Settings(), PullRequestEvent("o", "r", 1))
    assert len(files) == 1
    assert files[0].path == "a.py"


def test_render():
    out = diff._render([ChangedFile("a.py", "modified", "PATCH")])
    assert "--- a.py (modified)" in out
    assert "PATCH" in out


def test_apply_budget_passthrough():
    assert diff._apply_budget("short", 100) == "short"


def test_apply_budget_truncates():
    out = diff._apply_budget("x" * 100, 10)
    assert out.startswith("x" * 10)
    assert "truncated" in out


def test_collect_diff_filters(monkeypatch):
    files = [
        ChangedFile("src/a.py", "modified", "@@ a"),
        ChangedFile("poetry.lock", "modified", "@@ lock"),
        ChangedFile("img.png", "added", ""),
    ]
    monkeypatch.setattr(diff, "fetch_changed_files", lambda s, e: files)
    s = Settings()
    s.exclude = ["**/*.lock"]
    out = diff.collect_diff(s, PullRequestEvent("o", "r", 1))
    assert "src/a.py" in out
    assert "poetry.lock" not in out
    assert "img.png" not in out


def test_collect_diff_truncates(monkeypatch):
    monkeypatch.setattr(
        diff, "fetch_changed_files", lambda s, e: [ChangedFile("a.py", "modified", "y" * 500)]
    )
    s = Settings()
    s.exclude = []
    s.max_diff_bytes = 50
    out = diff.collect_diff(s, PullRequestEvent("o", "r", 1))
    assert "truncated" in out


def test_long_path_skips_pathological_matching():
    # `**/*a*a*a*a*b` backtracks super-linearly; an attacker-supplied path must not
    # be able to grow the input it backtracks over.
    started = time.time()
    assert not diff.is_excluded("a" * 4096, ["**/*a*a*a*a*b"])
    assert time.time() - started < 0.1
