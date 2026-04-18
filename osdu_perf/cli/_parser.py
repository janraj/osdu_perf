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

    run_k8s = run_subs.add_parser(
        "k8s",
        help="Run distributed Locust on AKS (build image, push to ACR, apply Job).",
    )
    _add_run_common_args(run_k8s)
    run_k8s.add_argument(
        "--namespace",
        help="Override aks.namespace from config (default: 'perf').",
    )
    run_k8s.add_argument(
        "--image-tag",
        help="Override the auto-generated image tag (default: derived from run name).",
    )
    run_k8s.add_argument(
        "--no-build",
        action="store_true",
        help="Skip docker build; reuse the image already in ACR.",
    )
    run_k8s.add_argument(
        "--no-push",
        action="store_true",
        help="Build the image but do not push to ACR (local docker only).",
    )
    run_k8s.add_argument(
        "--no-logs",
        action="store_true",
        help="Apply manifests then exit; do not stream master logs.",
    )
    run_k8s.add_argument(
        "--web-ui",
        action="store_true",
        help=(
            "Run Locust in web-UI mode (no --headless, no --run-time). "
            "The master pod stays up; port-forward 8089 to drive runs from the browser. "
            "Telemetry to Kusto is disabled in this mode (UI-driven runs are interactive)."
        ),
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

    # setup -----------------------------------------------------------
    setup = subparsers.add_parser(
        "setup", help="Provision external dependencies (Kusto tables, etc.)."
    )
    setup_subs = setup.add_subparsers(dest="target", required=True)

    setup_kusto = setup_subs.add_parser(
        "kusto",
        help="Create/update the LocustMetricsV2 / LocustTestSummaryV2 / "
        "LocustExceptionsV2 / LocustRequestTimeSeriesV2 tables.",
    )
    setup_kusto.add_argument(
        "--directory",
        default=".",
        help="Project directory holding azure_config.yaml (default: cwd).",
    )
    setup_kusto.add_argument(
        "--cluster-uri",
        help="Override kusto_export.cluster_uri from azure_config.yaml.",
    )
    setup_kusto.add_argument(
        "--database",
        help="Override kusto_export.database from azure_config.yaml.",
    )
    setup_kusto.add_argument(
        "--print-only",
        action="store_true",
        help="Print the KQL commands that would run without executing them.",
    )

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
    parser.add_argument(
        "--azure-config",
        help=(
            "Path to the azure_config.yaml file to use (relative to --directory "
            "or absolute). Lets one project hold multiple cluster configs, e.g. "
            "'config/azure_config.yaml' vs 'config/azure_config_aks2.yaml'. "
            "For 'run k8s', the same path is bundled into the image and read by "
            "the pod via the OSDU_PERF_AZURE_CONFIG env var."
        ),
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
