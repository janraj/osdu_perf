from unittest.mock import patch

from azure.core.credentials import AccessToken

from osdu_perf.operations.auth import (
    AzureCliStrategy,
    AzureTokenManager,
    ManagedIdentityStrategy,
)


def test_azure_cli_strategy_uses_access_token_and_cache():
    scope = "https://management.azure.com/.default"

    with patch("osdu_perf.operations.auth.AzureCliCredential") as credential_type:
        credential = credential_type.return_value
        credential.get_token.return_value = AccessToken("cli-token", 2_000_000_000)
        strategy = AzureCliStrategy()

        assert strategy.get_token(scope) == "cli-token"
        assert strategy.get_token(scope) == "cli-token"

    credential.get_token.assert_called_once_with(scope)


def test_managed_identity_strategy_uses_access_token_and_expected_scope():
    client_id = "managed-identity-client-id"
    expected_scope = f"api://{client_id}/.default"

    with patch("osdu_perf.operations.auth.ManagedIdentityCredential") as credential_type:
        credential = credential_type.return_value
        credential.get_token.return_value = AccessToken("mi-token", 2_000_000_000)
        strategy = ManagedIdentityStrategy(client_id=client_id)

        assert strategy.get_token("ignored-scope") == "mi-token"
        assert strategy.get_token("ignored-scope") == "mi-token"

    credential_type.assert_called_once_with(client_id=client_id)
    credential.get_token.assert_called_once_with(expected_scope)


def test_token_manager_returns_supplied_token_without_credential_request():
    with patch("osdu_perf.operations.auth.AzureCliCredential") as credential_type:
        manager = AzureTokenManager(token="supplied-token")

        assert manager.get_access_token("scope") == "supplied-token"

    credential_type.return_value.get_token.assert_not_called()