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
    args = parser.parse_args(
        [
            "run",
            "azure",
            "--scenario",
            "smoke",
            "--load-test-name",
            "alt-1",
        ]
    )
    assert args.command == "run"
    assert args.target == "azure"
    assert args.scenario == "smoke"
    assert args.load_test_name == "alt-1"


def test_run_local_load_shape_overrides_parse() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "local",
            "--users",
            "42",
            "--spawn-rate",
            "3",
            "--run-time",
            "90s",
            "--engine-instances",
            "2",
            "--test-run-id-prefix",
            "smoke",
            "--test-name",
            "nightly",
        ]
    )
    assert args.users == 42
    assert args.spawn_rate == 3
    assert args.run_time == "90s"
    assert args.engine_instances == 2
    assert args.test_run_id_prefix == "smoke"
    assert args.test_name == "nightly"


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
    assert result.spawn_rate == 2  # untouched
    assert result.run_time == "5m"
    assert result.engine_instances == 1  # untouched

    class _Resolved:
        test_run_id_prefix = "perf"
        test_name = "tn"
        scenario = "search_query"

    # CLI override wins, with test_name prepended
    assert (
        resolved_test_run_id_prefix(
            _Resolved(),
            argparse.Namespace(test_run_id_prefix="smoke", test_name=None),
        )
        == "tn-smoke"
    )
    # Fallback to resolved config, also prepended
    assert (
        resolved_test_run_id_prefix(
            _Resolved(),
            argparse.Namespace(test_run_id_prefix=None, test_name=None),
        )
        == "tn-perf"
    )
    # Idempotent if already prefixed
    assert (
        resolved_test_run_id_prefix(
            _Resolved(),
            argparse.Namespace(test_run_id_prefix="tn-base", test_name=None),
        )
        == "tn-base"
    )


def test_resolved_test_name_precedence() -> None:
    import argparse

    from osdu_perf.cli.commands._run_common import resolved_test_name

    class _R:
        scenario = "search_query"
        test_name = "smoke"

    # CLI wins
    assert resolved_test_name(_R(), argparse.Namespace(test_name="nightly")) == "nightly"
    # Config wins when CLI absent
    assert resolved_test_name(_R(), argparse.Namespace(test_name=None)) == "smoke"

    # Fallback to scenario
    class _R2:
        scenario = "search_query"
        test_name = None

    assert resolved_test_name(_R2(), argparse.Namespace(test_name=None)) == "search_query"
    # Blank CLI value falls through
    assert resolved_test_name(_R(), argparse.Namespace(test_name="  ")) == "smoke"


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


def test_setup_kusto_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(["setup", "kusto"])
    assert args.command == "setup"
    assert args.target == "kusto"
    assert args.directory == "."
    assert args.cluster_uri is None
    assert args.database is None
    assert args.print_only is False


def test_setup_kusto_overrides() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "setup",
            "kusto",
            "--directory",
            "/tmp/proj",
            "--cluster-uri",
            "https://c.kusto.windows.net",
            "--database",
            "mydb",
            "--print-only",
        ]
    )
    assert args.target == "kusto"
    assert args.directory == "/tmp/proj"
    assert args.cluster_uri == "https://c.kusto.windows.net"
    assert args.database == "mydb"
    assert args.print_only is True


def test_setup_requires_target() -> None:
    import pytest

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["setup"])


def test_run_k8s_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "k8s"])
    assert args.command == "run"
    assert args.target == "k8s"
    assert args.namespace is None
    assert args.image_tag is None
    assert args.no_build is False
    assert args.no_push is False
    assert args.no_logs is False


def test_run_k8s_overrides() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "k8s",
            "--namespace",
            "perf-east",
            "--image-tag",
            "v42",
            "--no-build",
            "--no-push",
            "--no-logs",
            "--users",
            "20",
        ]
    )
    assert args.target == "k8s"
    assert args.namespace == "perf-east"
    assert args.image_tag == "v42"
    assert args.no_build is True
    assert args.no_push is True
    assert args.no_logs is True
    assert args.users == 20
