import pr_reviewer.github.comments as gh
from pr_reviewer.config import Settings
from pr_reviewer.models import ChangedFile, Finding, PullRequestEvent


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


def test_summary_body_fail_on_findings_footer():
    body = gh._summary_body([], [], True)
    assert "can fail the build" in body
    assert "never fails your build" not in body


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


def test_commentable_map(monkeypatch):
    monkeypatch.setattr(
        gh, "fetch_changed_files", lambda s, e: [ChangedFile("a.py", "modified", "@@ -1 +1 @@\n+x")]
    )
    m = gh._commentable_map(Settings(), PullRequestEvent("o", "r", 1))
    assert m == {"a.py": {1}}


def test_delete_stale_inline(monkeypatch):
    deleted = []
    monkeypatch.setattr(
        gh,
        "_paginate",
        lambda s, url: [
            {"id": 1, "body": "mine " + gh._INLINE_MARKER},
            {"id": 2, "body": "a human comment"},
        ],
    )
    monkeypatch.setattr(gh, "_delete", lambda s, url: deleted.append(url))
    gh._delete_stale_inline(Settings(), PullRequestEvent("o", "r", 3))
    assert len(deleted) == 1
    assert deleted[0].endswith("/pulls/comments/1")


def test_find_comment_stops_at_first_page(monkeypatch):
    # _paginate is lazy, so a marker on page 1 must not fetch the pages behind it.
    import pr_reviewer.github.client as client

    pages = []

    class FakeResp:
        def __init__(self, items):
            self._items = items

        def json(self):
            return self._items

    def fake_get(settings, url, params=None):
        page = params["page"]
        pages.append(page)
        body = gh._SUMMARY_MARKER if page == 1 else "someone else"
        return FakeResp([{"id": page * 100 + i, "body": body} for i in range(100)])

    monkeypatch.setattr(client, "_get", fake_get)
    found = gh._find_comment(Settings(), PullRequestEvent("o", "r", 1), gh._SUMMARY_MARKER)
    assert found == 100
    assert pages == [1]


def test_sync_inline_posts_review(monkeypatch):
    posted = {}
    monkeypatch.setattr(gh, "_delete_stale_inline", lambda s, e: None)
    monkeypatch.setattr(gh, "_post", lambda s, url, payload: posted.update(url=url, payload=payload))
    gh._sync_inline(Settings(), PullRequestEvent("o", "r", 3), [Finding("a.py", 5, "high", "bug")])
    assert posted["url"].endswith("/pulls/3/reviews")
    assert posted["payload"]["event"] == "COMMENT"
    assert posted["payload"]["comments"][0] == {
        "path": "a.py",
        "line": 5,
        "side": "RIGHT",
        "body": posted["payload"]["comments"][0]["body"],
    }
    assert gh._INLINE_MARKER in posted["payload"]["comments"][0]["body"]


def test_sync_inline_skips_post_when_empty(monkeypatch):
    monkeypatch.setattr(gh, "_delete_stale_inline", lambda s, e: None)
    monkeypatch.setattr(
        gh, "_post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not post"))
    )
    gh._sync_inline(Settings(), PullRequestEvent("o", "r", 3), [])


def test_post_review_routes_findings(monkeypatch):
    monkeypatch.setattr(
        gh, "fetch_changed_files", lambda s, e: [ChangedFile("a.py", "modified", "@@ -1 +1,2 @@\n+x\n+y")]
    )
    summary, inline = {}, {}
    monkeypatch.setattr(
        gh, "_sync_summary", lambda s, e, f, u: summary.update(findings=f, unanchored=u)
    )
    monkeypatch.setattr(gh, "_sync_inline", lambda s, e, a: inline.update(anchored=a))
    findings = [Finding("a.py", 1, "high", "anchored"), Finding("a.py", 99, "low", "floating")]
    gh.post_review(Settings(), PullRequestEvent("o", "r", 3), findings)
    assert [f.message for f in inline["anchored"]] == ["anchored"]
    assert [f.message for f in summary["unanchored"]] == ["floating"]
    assert summary["findings"] == findings
