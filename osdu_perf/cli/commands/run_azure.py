"""`osdu_perf run azure`."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from ...auth import TokenProvider
from ...azure import AzureRunner
from ...azure.runner import AzureRunInputs
from ...config import load_config
from ...errors import ConfigError
from ._run_common import (
    apply_profile_overrides,
    parse_label_overrides,
    resolved_test_name,
    resolved_test_run_id_prefix,
)


def run(args: argparse.Namespace) -> int:
    project_dir = Path(args.directory).resolve()
    config = load_config(project_dir)

    if args.load_test_name:
        config = replace(
            config,
            azure_load_test=replace(config.azure_load_test, name=args.load_test_name),
        )

    env = config.osdu_env
    host = args.host or env.host
    partition = args.partition or env.partition
    app_id = args.app_id or env.app_id
    if not (host and partition and app_id):
        raise ConfigError("host, partition, and app_id must all be provided.")

    resolved = config.resolve(scenario=args.scenario, profile=args.profile)
    profile = apply_profile_overrides(resolved.profile, args)
    prefix = resolved_test_run_id_prefix(resolved, args)
    if prefix != config.test_run_id_prefix:
        config = replace(config, test_run_id_prefix=prefix)
    test_name = resolved_test_name(resolved, args)
    extra_labels = parse_label_overrides(args)
    merged_labels: dict[str, str] = {str(k): str(v) for k, v in resolved.labels.items()}
    merged_labels.update({str(k): str(v) for k, v in extra_labels.items()})
    bearer = args.bearer_token or TokenProvider(explicit_token=args.bearer_token).get_token(app_id)

    inputs = AzureRunInputs(
        host=host,
        partition=partition,
        app_id=app_id,
        osdu_token=bearer,
        test_directory=project_dir,
        profile=profile,
        labels=merged_labels,
        scenario=resolved.scenario,
        test_run_id_prefix=prefix,
        profile_name=resolved.profile_name,
        test_name=test_name,
    )
    runner = AzureRunner(config)
    result = runner.run(inputs)
    _print_run_summary(result)
    return 0


def _print_run_summary(result: dict) -> None:
    labels = result.get("labels") or {}
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "(none)"
    lines = [
        "",
        "=" * 72,
        "Azure Load Test run started",
        "=" * 72,
        f"  Scenario         : {result.get('scenario')}",
        f"  Test name        : {result.get('testName')}",
        f"  Profile          : {result.get('profileName')}",
        f"  Test ID          : {result.get('testId')}",
        f"  Test Run ID      : {result.get('testRunId')}",
        f"  Users            : {result.get('users')}",
        f"  Spawn rate       : {result.get('spawnRate')}",
        f"  Run time         : {result.get('runTime')}",
        f"  Engine instances : {result.get('engineInstances')}",
        f"  Host             : {result.get('host')}",
        f"  Partition        : {result.get('partition')}",
        f"  App ID           : {result.get('appId')}",
        f"  Labels           : {labels_str}",
        f"  ALT resource     : {result.get('loadTestResource')} (rg={result.get('resourceGroup')})",
        f"  Subscription     : {result.get('subscriptionId')}",
        f"  Portal           : {result.get('portalUrl')}",
        "=" * 72,
        "",
    ]
    print("\n".join(lines))
