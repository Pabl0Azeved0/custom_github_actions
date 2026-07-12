from pr_reviewer import github_api as gh
from pr_reviewer.github_api import ChangedFile


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
