"""Tests for the CLI argparse layer."""

import pytest

from osdu_perf.cli._parser import build_parser


def test_build_parser_accepts_init_with_sample() -> None:
    parser = build_parser()
    args = parser.parse_args(["init", "--sample", "search_query"])
    assert args.command == "init"
    assert args.sample == "search_query"


def test_run_local_requires_scenario() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "local"])


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


def test_version_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.command == "version"
