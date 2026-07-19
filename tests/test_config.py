import pytest

from pr_reviewer.config import Settings
from pr_reviewer.llm.groq_provider import GroqProvider
from pr_reviewer.llm.provider import LLMError, get_provider


def test_settings_read_input_env(monkeypatch):
    monkeypatch.setenv("INPUT_LLM-PROVIDER", "groq")
    monkeypatch.setenv("INPUT_MAX-FINDINGS", "3")
    monkeypatch.setenv("INPUT_FAIL-ON-FINDINGS", "true")
    monkeypatch.setenv("INPUT_EXCLUDE", "**/*.lock, **/dist/**\n**/*.min.js")
    s = Settings()
    assert s.llm_provider == "groq"
    assert s.max_findings == 3
    assert s.fail_on_findings is True
    assert "**/*.lock" in s.exclude
    assert "**/dist/**" in s.exclude
    assert "**/*.min.js" in s.exclude


def test_bare_env_fallback(monkeypatch):
    monkeypatch.setenv("PR_REVIEWER_LOCAL", "1")
    monkeypatch.delenv("INPUT_LLM-MODEL", raising=False)
    monkeypatch.setenv("LLM_MODEL", "some-model")
    assert Settings().llm_model == "some-model"


def test_bare_env_ignored_without_local_flag(monkeypatch):
    # A .env committed by a PR author must not influence the Action.
    monkeypatch.delenv("PR_REVIEWER_LOCAL", raising=False)
    monkeypatch.delenv("INPUT_SLACK-WEBHOOK", raising=False)
    monkeypatch.setenv("SLACK_WEBHOOK", "http://attacker.example/exfil")
    assert Settings().slack_webhook is None


def test_max_findings_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("INPUT_MAX-FINDINGS", "not-a-number")
    assert Settings().max_findings == 10


def test_get_provider_groq():
    s = Settings()
    s.llm_provider = "groq"
    s.llm_api_key = "key"
    assert isinstance(get_provider(s), GroqProvider)


def test_get_provider_requires_key():
    s = Settings()
    s.llm_provider = "groq"
    s.llm_api_key = None
    with pytest.raises(LLMError):
        get_provider(s)


def test_get_provider_unknown():
    s = Settings()
    s.llm_provider = "nope"
    s.llm_api_key = "key"
    with pytest.raises(LLMError):
        get_provider(s)
