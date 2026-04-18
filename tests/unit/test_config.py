"""Tests for :mod:`osdu_perf.config`."""

from pathlib import Path

import pytest

from osdu_perf.config import load_from_paths
from osdu_perf.errors import ConfigError, ScenarioNotFoundError


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _test_yaml(extra: str = "") -> str:
    return (
        """
osdu_environment:
  host: https://example.com
  partition: opendes
  app_id: abc-123
labels:
  version: "25.2.35"
profiles:
  U50_T15M:  { users: 50,  spawn_rate: 5,  run_time: "15m" }
  U100_T15M: { users: 100, spawn_rate: 10, run_time: "15m" }
  U200_T30M: { users: 200, spawn_rate: 20, run_time: "30m" }
"""
        + extra
    )


# ---------------------------------------------------------------------
# azure_config.yaml
# ---------------------------------------------------------------------
def test_azure_load_test_and_kusto_export_are_separate_sections(tmp_path: Path) -> None:
    azure = _write(
        tmp_path,
        "azure.yaml",
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
    test = _write(tmp_path, "t.yaml", _test_yaml())
    config = load_from_paths(azure, test)

    assert config.azure_load_test.subscription_id == "sub-1"
    assert config.azure_load_test.name == "my-alt"
    assert config.azure_load_test.allow_resource_creation is True

    assert config.kusto_export.is_configured
    assert config.kusto_export.database == "perf-db"
    assert config.kusto_export.ingest_uri == "https://ingest-foo.eastus.kusto.windows.net"


# ---------------------------------------------------------------------
# test_config.yaml
# ---------------------------------------------------------------------
def test_osdu_env_and_labels_come_from_test_config(tmp_path: Path) -> None:
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml())
    config = load_from_paths(azure, test)
    assert config.osdu_env.host == "https://example.com"
    assert config.labels == {"version": "25.2.35"}


def test_profiles_are_parsed(tmp_path: Path) -> None:
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml())
    config = load_from_paths(azure, test)
    assert set(config.profiles) == {"u50_t15m", "u100_t15m", "u200_t30m"}
    assert config.profiles["u100_t15m"].users == 100
    assert config.profiles["u200_t30m"].run_time == "30m"


# ---------------------------------------------------------------------
# resolve() precedence
# ---------------------------------------------------------------------
def test_cli_scenario_and_profile_win(tmp_path: Path) -> None:
    extra = """
scenario_defaults:
  smoke:
    profile: U50_T15M
run_scenario:
  scenario: other_thing
  profile: U100_T15M
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)

    resolved = config.resolve(scenario="smoke", profile="U200_T30M")
    assert resolved.scenario == "smoke"
    assert resolved.profile_name == "U200_T30M"
    assert resolved.profile.users == 200


def test_scenario_cli_uses_scenario_defaults_profile(tmp_path: Path) -> None:
    extra = """
scenario_defaults:
  smoke:
    profile: U100_T15M
    metadata:
      kind: query
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)

    resolved = config.resolve(scenario="smoke")
    assert resolved.profile_name == "U100_T15M"
    assert resolved.labels == {"version": "25.2.35", "kind": "query"}


def test_run_scenario_fills_in_when_cli_omits_scenario(tmp_path: Path) -> None:
    extra = """
scenario_defaults:
  smoke:
    profile: U50_T15M
run_scenario:
  scenario: smoke
  profile: U200_T30M
  labels:
    triggered_by: nightly
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)

    resolved = config.resolve()
    assert resolved.scenario == "smoke"
    # run_scenario.profile beats scenario_defaults[smoke].profile
    assert resolved.profile_name == "U200_T30M"
    # run_scenario.labels merge only when run_scenario supplied the scenario
    assert resolved.labels == {
        "version": "25.2.35",
        "triggered_by": "nightly",
    }


def test_run_scenario_labels_ignored_when_scenario_is_explicit(tmp_path: Path) -> None:
    extra = """
scenario_defaults:
  smoke:
    profile: U50_T15M
run_scenario:
  scenario: smoke
  labels:
    triggered_by: nightly
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)

    resolved = config.resolve(scenario="smoke")
    assert "triggered_by" not in resolved.labels


def test_missing_scenario_raises(tmp_path: Path) -> None:
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml())
    config = load_from_paths(azure, test)
    with pytest.raises(ScenarioNotFoundError):
        config.resolve()


def test_no_profile_anywhere_raises(tmp_path: Path) -> None:
    extra = """
scenario_defaults:
  smoke: { profile: U100_T15M }
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)
    # 'other' has no scenario_defaults entry and no --profile provided
    with pytest.raises(ConfigError):
        config.resolve(scenario="other")


def test_unknown_profile_raises(tmp_path: Path) -> None:
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml())
    config = load_from_paths(azure, test)
    with pytest.raises(ConfigError):
        config.resolve(scenario="anything", profile="does_not_exist")


def test_scenario_defaults_missing_profile_raises(tmp_path: Path) -> None:
    extra = """
scenario_defaults:
  broken: {}
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    with pytest.raises(ConfigError):
        load_from_paths(azure, test)


# ---------------------------------------------------------------------
# test_run_id_prefix precedence
# ---------------------------------------------------------------------
def test_run_scenario_prefix_wins_over_top_level(tmp_path: Path) -> None:
    extra = """
test_run_id_prefix: legacy
run_scenario:
  scenario: smoke
  profile: U50_T15M
  test_run_id_prefix: nightly
scenario_defaults:
  smoke: { profile: U50_T15M }
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)
    assert config.test_run_id_prefix == "nightly"


def test_top_level_prefix_used_when_run_scenario_omits_it(tmp_path: Path) -> None:
    extra = """
test_run_id_prefix: legacy
run_scenario:
  scenario: smoke
  profile: U50_T15M
scenario_defaults:
  smoke: { profile: U50_T15M }
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)
    assert config.test_run_id_prefix == "legacy"


def test_prefix_defaults_to_perf_when_neither_is_set(tmp_path: Path) -> None:
    extra = """
scenario_defaults:
  smoke: { profile: U50_T15M }
run_scenario:
  scenario: smoke
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    config = load_from_paths(azure, test)
    assert config.test_run_id_prefix == "perf"


def test_top_level_prefix_emits_deprecation_warning(tmp_path: Path, caplog) -> None:
    import logging

    extra = """
test_run_id_prefix: legacy
scenario_defaults:
  smoke: { profile: U50_T15M }
run_scenario:
  scenario: smoke
"""
    azure = _write(tmp_path, "a.yaml", "")
    test = _write(tmp_path, "t.yaml", _test_yaml(extra))
    with caplog.at_level(logging.WARNING, logger="osdu_perf.config.loader"):
        load_from_paths(azure, test)
    assert any("deprecated" in r.getMessage() for r in caplog.records)
