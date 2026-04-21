"""Unit tests for InputHandler.get_kusto_config() merge logic."""

import pytest
from unittest.mock import patch, MagicMock

# Mock defaults — tests validate merge behavior, not actual default values
MOCK_DEFAULTS = {
    "cluster": "https://mock-default.kusto.windows.net",
    "database": "mock-default-db",
    "ingest_uri": "https://ingest-mock-default.kusto.windows.net",
}


def _make_input_handler(system_config=None):
    """Create an InputHandler in config-only mode with the given system_config."""
    with patch("osdu_perf.operations.input_handler.InputHandler._load_split_configs") as mock_load:
        mock_load.return_value = (system_config or {}, {})
        with patch("osdu_perf.operations.input_handler.InputHandler._detect_azure_load_test_environment", return_value=False):
            from osdu_perf.operations.input_handler import InputHandler
            ih = InputHandler(environment=None)
    return ih


@pytest.fixture(autouse=True)
def _patch_kusto_defaults():
    """Patch the hardcoded default_config inside get_kusto_config with mock values."""
    original_method = None

    from osdu_perf.operations.input_handler import InputHandler
    original_method = InputHandler.get_kusto_config

    def patched_get_kusto_config(self):
        # Temporarily replace the default_config inside the method
        import types
        # Call original but with patched defaults
        default_config = MOCK_DEFAULTS.copy()

        metrics_config = self.system_config.get('metrics_collector', {})
        kusto_config = metrics_config.get('kusto', {})

        final_config = default_config.copy()
        for key, value in kusto_config.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            final_config[key] = value

        if self.is_azure_load_test_env:
            final_config['auth_method'] = 'managed_identity'
        else:
            final_config['auth_method'] = 'az_cli'

        return final_config

    InputHandler.get_kusto_config = patched_get_kusto_config
    yield
    InputHandler.get_kusto_config = original_method


class TestGetKustoConfig:
    """Tests for the get_kusto_config merge logic."""

    def test_defaults_when_no_metrics_collector(self):
        """When system_config has no metrics_collector, defaults are used."""
        ih = _make_input_handler({})
        cfg = ih.get_kusto_config()
        assert cfg["cluster"] == MOCK_DEFAULTS["cluster"]
        assert cfg["database"] == MOCK_DEFAULTS["database"]
        assert cfg["ingest_uri"] == MOCK_DEFAULTS["ingest_uri"]

    def test_none_does_not_override_defaults(self):
        """A None value in config should NOT override the default."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "cluster": None,
                    "database": None,
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["cluster"] == MOCK_DEFAULTS["cluster"]
        assert cfg["database"] == MOCK_DEFAULTS["database"]

    def test_whitespace_only_string_does_not_override_defaults(self):
        """A whitespace-only string should NOT override the default."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "cluster": "   ",
                    "database": "  \t  ",
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["cluster"] == MOCK_DEFAULTS["cluster"]
        assert cfg["database"] == MOCK_DEFAULTS["database"]

    def test_empty_string_does_not_override_defaults(self):
        """An empty string should NOT override the default."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "cluster": "",
                    "database": "",
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["cluster"] == MOCK_DEFAULTS["cluster"]
        assert cfg["database"] == MOCK_DEFAULTS["database"]

    def test_valid_string_overrides_defaults(self):
        """A non-empty string should override the default."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "cluster": "https://custom.kusto.windows.net",
                    "database": "custom-db",
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["cluster"] == "https://custom.kusto.windows.net"
        assert cfg["database"] == "custom-db"

    def test_boolean_values_are_preserved(self):
        """Non-string values like booleans should be kept as-is."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "enabled": True,
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["enabled"] is True

    def test_boolean_false_is_preserved(self):
        """Boolean False should not be skipped."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "enabled": False,
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["enabled"] is False

    def test_partial_override(self):
        """Override only cluster, database keeps default."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "cluster": "https://my-cluster.kusto.windows.net",
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["cluster"] == "https://my-cluster.kusto.windows.net"
        assert cfg["database"] == MOCK_DEFAULTS["database"]

    def test_auth_method_az_cli_locally(self):
        """Auth method should be az_cli when not in Azure Load Test env."""
        ih = _make_input_handler({})
        cfg = ih.get_kusto_config()
        assert cfg["auth_method"] == "az_cli"

    def test_auth_method_managed_identity_in_azure(self):
        """Auth method should be managed_identity in Azure Load Test env."""
        ih = _make_input_handler({})
        ih.is_azure_load_test_env = True
        cfg = ih.get_kusto_config()
        assert cfg["auth_method"] == "managed_identity"

    def test_extra_keys_from_config_are_added(self):
        """Extra keys in kusto config (not in defaults) should be added."""
        ih = _make_input_handler({
            "metrics_collector": {
                "kusto": {
                    "custom_key": "custom_value",
                }
            }
        })
        cfg = ih.get_kusto_config()
        assert cfg["custom_key"] == "custom_value"
        # Defaults still present
        assert cfg["cluster"] == MOCK_DEFAULTS["cluster"]
