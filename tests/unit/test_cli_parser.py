"""Tests for the CLI argparse layer."""

from osdu_perf.cli._parser import build_parser


def test_build_parser_accepts_init_with_sample() -> None:
    parser = build_parser()
    args = parser.parse_args(["init", "--sample", "search_query"])
    assert args.command == "init"
    assert args.sample == "search_query"


def test_run_local_scenario_is_optional() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "local"])
    assert args.command == "run"
    assert args.target == "local"
    assert args.scenario is None
    assert args.profile is None


def test_run_azure_forwards_flags() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "run",
        "azure",
        "--scenario",
        "smoke",
        "--load-test-name",
        "alt-1",
    ])
    assert args.command == "run"
    assert args.target == "azure"
    assert args.scenario == "smoke"
    assert args.load_test_name == "alt-1"


def test_run_local_load_shape_overrides_parse() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "run", "local",
        "--users", "42",
        "--spawn-rate", "3",
        "--run-time", "90s",
        "--engine-instances", "2",
        "--test-run-id-prefix", "smoke",
    ])
    assert args.users == 42
    assert args.spawn_rate == 3
    assert args.run_time == "90s"
    assert args.engine_instances == 2
    assert args.test_run_id_prefix == "smoke"


def test_apply_profile_overrides_replaces_fields() -> None:
    import argparse

    from osdu_perf.cli.commands._run_common import (
        apply_profile_overrides,
        resolved_test_run_id_prefix,
    )
    from osdu_perf.config import PerformanceProfile

    base = PerformanceProfile(users=10, spawn_rate=2, run_time="60s", engine_instances=1)
    args = argparse.Namespace(users=100, spawn_rate=None, run_time="5m", engine_instances=None)
    result = apply_profile_overrides(base, args)
    assert result.users == 100
    assert result.spawn_rate == 2        # untouched
    assert result.run_time == "5m"
    assert result.engine_instances == 1  # untouched

    class _Resolved:
        test_run_id_prefix = "perf"

    # CLI override wins
    assert (
        resolved_test_run_id_prefix(
            _Resolved(), argparse.Namespace(test_run_id_prefix="smoke")
        )
        == "smoke"
    )
    # Fallback to resolved config
    assert (
        resolved_test_run_id_prefix(
            _Resolved(), argparse.Namespace(test_run_id_prefix=None)
        )
        == "perf"
    )


def test_parse_label_overrides() -> None:
    import argparse

    import pytest

    from osdu_perf.cli.commands._run_common import parse_label_overrides

    # Empty -> empty
    assert parse_label_overrides(argparse.Namespace(label=[])) == {}
    # Multiple entries, trimming, and value may contain '='
    result = parse_label_overrides(
        argparse.Namespace(label=["build=42", "region=eastus", "raw=a=b"])
    )
    assert result == {"build": "42", "region": "eastus", "raw": "a=b"}
    # Malformed
    with pytest.raises(ValueError):
        parse_label_overrides(argparse.Namespace(label=["nope"]))
    with pytest.raises(ValueError):
        parse_label_overrides(argparse.Namespace(label=["=empty-key"]))


def test_version_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.command == "version"
