from pr_reviewer import github_api as gh
from pr_reviewer.config import Settings
from pr_reviewer.github_api import ChangedFile, PullRequestEvent


def test_is_excluded_lock_and_dist():
    pats = ["**/*.lock", "**/dist/**"]
    assert gh.is_excluded("poetry.lock", pats)
    assert gh.is_excluded("a/b/poetry.lock", pats)
    assert gh.is_excluded("dist/app.js", pats)
    assert gh.is_excluded("web/dist/app.js", pats)


def test_is_excluded_negatives():
    pats = ["**/*.lock", "**/dist/**"]
    assert not gh.is_excluded("src/app.py", pats)
    assert not gh.is_excluded("locket.py", pats)


def test_include_decision():
    ex = ["**/*.lock"]
    assert gh._include(ChangedFile("src/a.py", "modified", "@@ -1 +1 @@\n-x\n+y"), ex)
    assert not gh._include(ChangedFile("img.png", "added", ""), ex)
    assert not gh._include(ChangedFile("src/a.py", "removed", "@@"), ex)
    assert not gh._include(ChangedFile("poetry.lock", "modified", "@@"), ex)


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

    monkeypatch.setattr(gh, "_get", fake_get)
    files = gh.fetch_changed_files(Settings(), PullRequestEvent("o", "r", 1))
    assert len(files) == 1
    assert files[0].path == "a.py"


def test_render():
    out = gh._render([ChangedFile("a.py", "modified", "PATCH")])
    assert "--- a.py (modified)" in out
    assert "PATCH" in out


def test_apply_budget_passthrough():
    assert gh._apply_budget("short", 100) == "short"


def test_apply_budget_truncates():
    out = gh._apply_budget("x" * 100, 10)
    assert out.startswith("x" * 10)
    assert "truncated" in out


def test_collect_diff_filters(monkeypatch):
    files = [
        ChangedFile("src/a.py", "modified", "@@ a"),
        ChangedFile("poetry.lock", "modified", "@@ lock"),
        ChangedFile("img.png", "added", ""),
    ]
    monkeypatch.setattr(gh, "fetch_changed_files", lambda s, e: files)
    s = Settings()
    s.exclude = ["**/*.lock"]
    diff = gh.collect_diff(s, PullRequestEvent("o", "r", 1))
    assert "src/a.py" in diff
    assert "poetry.lock" not in diff
    assert "img.png" not in diff
