from pr_reviewer import github_api as gh
from pr_reviewer.config import Settings
from pr_reviewer.github_api import ChangedFile, PullRequestEvent
from pr_reviewer.review import Finding


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


def test_collect_diff_truncates(monkeypatch):
    monkeypatch.setattr(
        gh, "fetch_changed_files", lambda s, e: [ChangedFile("a.py", "modified", "y" * 500)]
    )
    s = Settings()
    s.exclude = []
    s.max_diff_bytes = 50
    out = gh.collect_diff(s, PullRequestEvent("o", "r", 1))
    assert "truncated" in out


def test_commentable_lines():
    patch = "@@ -10,3 +10,4 @@\n ctx\n+added1\n+added2\n-removed\n ctx2"
    # new-file lines: 10 ctx, 11 added1, 12 added2, (removed doesn't advance), 13 ctx2
    assert gh._commentable_lines(patch) == {10, 11, 12, 13}


def test_commentable_lines_only_added_are_new():
    patch = "@@ -1,0 +1,2 @@\n+x\n+y"
    assert gh._commentable_lines(patch) == {1, 2}


def test_split_findings():
    commentable = {"a.py": {5, 6}}
    anchored, unanchored = gh._split_findings(
        [
            Finding("a.py", 5, "high", "on a diff line"),
            Finding("a.py", 99, "low", "line not in diff"),
            Finding("b.py", 5, "low", "file not in diff"),
            Finding("a.py", 0, "low", "no line"),
        ],
        commentable,
    )
    assert [f.message for f in anchored] == ["on a diff line"]
    assert len(unanchored) == 3


def test_summary_body_no_findings():
    body = gh._summary_body([], [])
    assert gh._SUMMARY_MARKER in body
    assert "No findings" in body


def test_summary_body_lists_unanchored():
    unanchored = [Finding("a.py", 0, "high", "boom")]
    body = gh._summary_body(unanchored, unanchored)
    assert "Found **1** potential issue." in body
    assert "`a.py`" in body
    assert "boom" in body


def test_sync_summary_posts_when_absent(monkeypatch):
    calls = {}
    monkeypatch.setattr(gh, "_paginate", lambda s, url: [])
    monkeypatch.setattr(gh, "_post", lambda s, url, payload: calls.update(post=(url, payload)))
    monkeypatch.setattr(gh, "_patch", lambda s, url, payload: calls.update(patch=url))
    gh._sync_summary(Settings(), PullRequestEvent("o", "r", 7), [], [])
    assert "patch" not in calls
    assert "/issues/7/comments" in calls["post"][0]
    assert gh._SUMMARY_MARKER in calls["post"][1]["body"]


def test_sync_summary_patches_when_present(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        gh, "_paginate", lambda s, url: [{"id": 42, "body": gh._SUMMARY_MARKER + " old"}]
    )
    monkeypatch.setattr(gh, "_post", lambda s, url, payload: calls.update(post=url))
    monkeypatch.setattr(gh, "_patch", lambda s, url, payload: calls.update(patch=url))
    gh._sync_summary(Settings(), PullRequestEvent("o", "r", 7), [], [])
    assert "post" not in calls
    assert calls["patch"].endswith("/issues/comments/42")
