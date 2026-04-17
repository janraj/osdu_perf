"""Tests for :mod:`osdu_perf.config`."""

from pathlib import Path

import pytest

from osdu_perf.config import load_from_paths
from osdu_perf.errors import ScenarioNotFoundError


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_from_paths_returns_typed_config(tmp_path: Path) -> None:
    system = _write(
        tmp_path,
        "system.yaml",
        """
osdu_environment:
  host: https://example.com
  partition: opendes
  app_id: abc-123
test_metadata:
  performance_tier: flex
""",
    )
    test = _write(
        tmp_path,
        "test.yaml",
        """
test_settings:
  users: 5
scenarios:
  smoke:
    users: 20
    metadata:
      kind: smoke
""",
    )
    config = load_from_paths(system, test)
    assert config.osdu_env.host == "https://example.com"
    assert "smoke" in config.scenarios
    resolved = config.resolved_settings("smoke")
    assert resolved.users == 20


def test_scenario_missing_raises(tmp_path: Path) -> None:
    system = _write(tmp_path, "s.yaml", "osdu_environment: {}\n")
    test = _write(tmp_path, "t.yaml", "scenarios: {}\n")
    config = load_from_paths(system, test)
    with pytest.raises(ScenarioNotFoundError):
        config.scenario("nope")
