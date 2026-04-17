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
        default="storage_crud",
        help="Sample template to use (default: storage_crud).",
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
        help="Override azure_infra.azure_load_test.name from config.",
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
        required=True,
        help="Scenario name (must exist in config/test_config.yaml).",
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


__all__ = ["build_parser"]
