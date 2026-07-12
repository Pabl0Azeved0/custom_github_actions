from pr_reviewer import review as review_mod
from pr_reviewer.config import Settings

SAMPLE_DIFF = "--- path/to/file.py (modified)\n@@ -1,2 +1,2 @@\n-old\n+new\n"


def test_build_prompt_contains_key_pieces():
    s = Settings()
    s.max_findings = 7
    prompt = review_mod.build_prompt(s, SAMPLE_DIFF)
    assert "Do NOT report style" in prompt
    assert SAMPLE_DIFF in prompt
    assert "7" in prompt
