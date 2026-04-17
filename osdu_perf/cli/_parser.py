"""argparse wiring for the ``osdu_perf`` CLI."""

from __future__ import annotations

import argparse

from .._version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="osdu_perf",
        description="Performance testing framework for OSDU APIs.",
    )
    parser.add_argument("--version", action="version", version=f"osdu_perf {__version__}")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging and full tracebacks.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init ------------------------------------------------------------
    init = subparsers.add_parser("init", help="Scaffold a new test project.")
    init.add_argument(
        "--sample",
        default="search_query",
        help="Sample template to use (default: search_query).",
    )
    init.add_argument(
        "--directory",
        default=".",
        help="Target directory (default: current working directory).",
    )
    init.add_argument(
        "--list-samples",
        action="store_true",
        help="List available sample templates and exit.",
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )

    # run -------------------------------------------------------------
    run = subparsers.add_parser("run", help="Execute a load test.")
    run_subs = run.add_subparsers(dest="target", required=True)

    run_local = run_subs.add_parser("local", help="Run Locust locally.")
    _add_run_common_args(run_local)
    run_local.add_argument(
        "--headless",
        action="store_true",
        help="Run Locust in headless mode (no web UI).",
    )

    run_azure = run_subs.add_parser("azure", help="Run on Azure Load Testing.")
    _add_run_common_args(run_azure)
    run_azure.add_argument(
        "--load-test-name",
        help="Override azure_load_test.name from config.",
    )

    # validate --------------------------------------------------------
    validate = subparsers.add_parser(
        "validate", help="Validate configuration without running a test."
    )
    validate.add_argument(
        "--directory",
        default=".",
        help="Project directory to validate (default: cwd).",
    )

    # samples ---------------------------------------------------------
    subparsers.add_parser("samples", help="List bundled sample templates.")

    # version ---------------------------------------------------------
    subparsers.add_parser("version", help="Print the installed version.")

    return parser


def _add_run_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scenario",
        help=(
            "Scenario name. When omitted, falls back to "
            "'run_scenario.scenario' in test_config.yaml."
        ),
    )
    parser.add_argument(
        "--profile",
        help=(
            "Profile name from test_config.yaml:profiles. Overrides any "
            "default coming from scenario_defaults.<scenario>.profile or "
            "run_scenario.profile."
        ),
    )
    parser.add_argument(
        "--directory",
        default=".",
        help="Project directory (default: cwd).",
    )
    parser.add_argument("--host", help="Override osdu_environment.host.")
    parser.add_argument("--partition", help="Override osdu_environment.partition.")
    parser.add_argument("--app-id", help="Override osdu_environment.app_id.")
    parser.add_argument(
        "--bearer-token",
        help="Pre-acquired OSDU bearer token (bypasses az login).",
    )

    # Per-invocation load-shape overrides. Each wins over the resolved profile.
    parser.add_argument(
        "--users",
        type=int,
        help="Override the resolved profile's 'users' (concurrent Locust users).",
    )
    parser.add_argument(
        "--spawn-rate",
        type=int,
        help="Override the resolved profile's 'spawn_rate' (users started per second).",
    )
    parser.add_argument(
        "--run-time",
        help="Override the resolved profile's 'run_time' (e.g. '15m', '90s', '2h').",
    )
    parser.add_argument(
        "--engine-instances",
        type=int,
        help="Override the resolved profile's 'engine_instances' (ALT only).",
    )
    parser.add_argument(
        "--test-name",
        help=(
            "ALT test name (stable across runs). Overrides 'run_scenario.test_name' "
            "in test_config.yaml. The ALT test ID becomes '<scenario>_<test_name>' "
            "and each invocation creates a new run under that test."
        ),
    )
    parser.add_argument(
        "--test-run-id-prefix",
        help=(
            "Override the 'test_run_id_prefix' from test_config.yaml "
            "(default 'perf'). The generated run id is "
            "'<scenario>_<test_name>_<prefix>_<UTC_ts>'."
        ),
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Extra label merged on top of resolved labels (top-level 'labels' + "
            "scenario metadata + run_scenario.labels). Repeatable: "
            "--label build=42 --label region=eastus."
        ),
    )


__all__ = ["build_parser"]
