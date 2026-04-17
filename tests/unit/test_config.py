"""Tests for :mod:`osdu_perf.config`."""

from pathlib import Path

import pytest

from osdu_perf.config import load_from_paths
from osdu_perf.errors import ConfigError, ScenarioNotFoundError


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_osdu_environment_and_metadata_come_from_test_config(tmp_path: Path) -> None:
    system = _write(tmp_path, "system.yaml", "azure_load_test:\n  location: eastus\n")
    test = _write(
        tmp_path,
        "test.yaml",
        """
osdu_environment:
  host: https://example.com
  partition: opendes
  app_id: abc-123
test_metadata:
  version: "25.2.35"
  build_id: "abc"
scenarios:
  smoke:
    users: 20
""",
    )
    config = load_from_paths(system, test)
    assert config.osdu_env.host == "https://example.com"
    assert config.test_metadata.as_dict() == {"version": "25.2.35", "build_id": "abc"}


def test_cli_profile_overrides_scenario_profile(tmp_path: Path) -> None:
    system = _write(tmp_path, "s.yaml", "")
    test = _write(
        tmp_path,
        "t.yaml",
        """
profiles:
  default: { users: 10 }
  flex:    { users: 100, run_time: "5m" }
scenarios:
  smoke:
    profile: default
""",
    )
    config = load_from_paths(system, test)
    assert config.resolved_settings("smoke").users == 10
    assert config.resolved_settings("smoke", profile_name="flex").users == 100
    assert config.resolved_settings("smoke", profile_name="flex").run_time == "5m"


def test_scenario_overrides_win_over_profile(tmp_path: Path) -> None:
    system = _write(tmp_path, "s.yaml", "")
    test = _write(
        tmp_path,
        "t.yaml",
        """
profiles:
  flex: { users: 100 }
scenarios:
  smoke:
    profile: flex
    users: 25
""",
    )
    config = load_from_paths(system, test)
    assert config.resolved_settings("smoke").users == 25


def test_default_profile_used_when_nothing_specified(tmp_path: Path) -> None:
    system = _write(tmp_path, "s.yaml", "")
    test = _write(
        tmp_path,
        "t.yaml",
        """
profiles:
  default: { users: 7 }
scenarios:
  smoke: {}
""",
    )
    config = load_from_paths(system, test)
    assert config.resolved_settings("smoke").users == 7


def test_falls_back_to_defaults_when_no_default_profile(tmp_path: Path) -> None:
    system = _write(tmp_path, "s.yaml", "")
    test = _write(
        tmp_path,
        "t.yaml",
        """
test_settings:
  users: 3
scenarios:
  smoke: {}
""",
    )
    config = load_from_paths(system, test)
    assert config.resolved_settings("smoke").users == 3


def test_unknown_profile_raises(tmp_path: Path) -> None:
    system = _write(tmp_path, "s.yaml", "")
    test = _write(
        tmp_path,
        "t.yaml",
        "profiles:\n  default: { users: 1 }\nscenarios:\n  smoke: {}\n",
    )
    config = load_from_paths(system, test)
    with pytest.raises(ConfigError):
        config.resolved_settings("smoke", profile_name="nope")


def test_scenario_missing_raises(tmp_path: Path) -> None:
    system = _write(tmp_path, "s.yaml", "")
    test = _write(tmp_path, "t.yaml", "scenarios: {}\n")
    config = load_from_paths(system, test)
    with pytest.raises(ScenarioNotFoundError):
        config.scenario("nope")


def test_azure_load_test_and_kusto_export_are_separate_sections(tmp_path: Path) -> None:
    system = _write(
        tmp_path,
        "system.yaml",
        """
azure_load_test:
  subscription_id: sub-1
  resource_group: rg-1
  location: westus2
  allow_resource_creation: true
  name: my-alt
kusto_export:
  cluster_uri: https://foo.eastus.kusto.windows.net
  database: perf-db
""",
    )
    test = _write(tmp_path, "test.yaml", "scenarios: {}\n")
    config = load_from_paths(system, test)

    assert config.azure_load_test.subscription_id == "sub-1"
    assert config.azure_load_test.resource_group == "rg-1"
    assert config.azure_load_test.location == "westus2"
    assert config.azure_load_test.allow_resource_creation is True
    assert config.azure_load_test.name == "my-alt"

    assert config.kusto_export.is_configured
    assert config.kusto_export.database == "perf-db"
    # ingest_uri auto-derived from cluster_uri
    assert config.kusto_export.ingest_uri == "https://ingest-foo.eastus.kusto.windows.net"

