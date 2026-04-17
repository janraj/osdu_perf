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
from ._run_common import apply_profile_overrides, resolved_test_run_id_prefix


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
    bearer = args.bearer_token or TokenProvider(explicit_token=args.bearer_token).get_token(app_id)

    inputs = AzureRunInputs(
        host=host,
        partition=partition,
        app_id=app_id,
        osdu_token=bearer,
        test_directory=project_dir,
        profile=profile,
        labels={str(k): str(v) for k, v in resolved.labels.items()},
        scenario=resolved.scenario,
        test_run_id_prefix=prefix,
    )
    runner = AzureRunner(config)
    result = runner.run(inputs)
    print(f"Started test run: {result.get('testRunId')}")
    return 0
