"""Tests for :class:`osdu_perf.auth.TokenProvider`."""

from unittest.mock import patch

from osdu_perf.auth import TokenProvider


def test_explicit_token_is_returned_verbatim() -> None:
    provider = TokenProvider(explicit_token="abc")
    assert provider.get_token("any-app-id") == "abc"


def test_env_token_is_used_when_available(monkeypatch) -> None:
    monkeypatch.setenv("ADME_BEARER_TOKEN", "env-token")
    provider = TokenProvider()
    assert provider.get_token("any-app-id") == "env-token"


def test_caches_per_app_id(monkeypatch) -> None:
    monkeypatch.delenv("ADME_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("AZURE_LOAD_TEST", raising=False)
    monkeypatch.delenv("LOCUST_HOST", raising=False)
    calls = {"n": 0}

    def fake(self, app_id):
        calls["n"] += 1
        return f"token-{app_id}"

    with patch.object(TokenProvider, "_azure_cli_token", fake):
        provider = TokenProvider()
        assert provider.get_token("app") == "token-app"
        assert provider.get_token("app") == "token-app"
        assert calls["n"] == 1
