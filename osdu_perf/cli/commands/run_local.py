"""`osdu_perf run local`."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from ...auth import TokenProvider
from ...config import load_config
from ...errors import ConfigError
from ...local import LocalRunInputs, LocalRunner, build_run_id
from ._run_common import (
    apply_profile_overrides,
    parse_label_overrides,
    resolved_test_name,
    resolved_test_run_id_prefix,
)


def run(args: argparse.Namespace) -> int:
    project_dir = Path(args.directory).resolve()
    config = load_config(project_dir)

    env = config.osdu_env
    host = args.host or env.host
    partition = args.partition or env.partition
    app_id = args.app_id or env.app_id
    if not (host and partition and app_id):
        raise ConfigError("host, partition, and app_id must all be provided.")

    resolved = config.resolve(scenario=args.scenario, profile=args.profile)
    profile = apply_profile_overrides(resolved.profile, args)
    prefix = resolved_test_run_id_prefix(resolved, args)
    test_name = resolved_test_name(resolved, args)
    extra_labels = parse_label_overrides(args)
    merged_labels: dict[str, str] = {str(k): str(v) for k, v in resolved.labels.items()}
    merged_labels.update({str(k): str(v) for k, v in extra_labels.items()})
    bearer = args.bearer_token or TokenProvider(explicit_token=args.bearer_token).get_token(app_id)

    partial_inputs = LocalRunInputs(
        host=host,
        partition=partition,
        app_id=app_id,
        bearer_token=bearer,
        scenario=resolved.scenario,
        profile=profile,
        locustfile=project_dir / "locustfile.py",
        headless=args.headless,
        test_run_id_prefix=prefix,
        extra_labels={str(k): str(v) for k, v in extra_labels.items()},
        test_name=test_name,
    )
    run_id = build_run_id(partial_inputs)
    inputs = replace(partial_inputs, run_id=run_id)
    _print_run_summary(
        scenario=resolved.scenario,
        test_name=test_name,
        profile_name=resolved.profile_name,
        run_id=run_id,
        profile=profile,
        host=host,
        partition=partition,
        app_id=app_id,
        labels=merged_labels,
        headless=args.headless,
        project_dir=project_dir,
    )
    return LocalRunner(config).run(inputs)


def _print_run_summary(
    *,
    scenario: str,
    test_name: str,
    profile_name: str | None,
    run_id: str,
    profile,
    host: str,
    partition: str,
    app_id: str,
    labels: dict[str, str],
    headless: bool,
    project_dir: Path,
) -> None:
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "(none)"
    lines = [
        "",
        "=" * 72,
        "Local Locust run starting",
        "=" * 72,
        f"  Scenario         : {scenario}",
        f"  Test name        : {test_name}",
        f"  Profile          : {profile_name}",
        f"  Test Run ID      : {run_id}",
        f"  Users            : {profile.users}",
        f"  Spawn rate       : {profile.spawn_rate}",
        f"  Run time         : {profile.run_time}",
        f"  Host             : {host}",
        f"  Partition        : {partition}",
        f"  App ID           : {app_id}",
        f"  Labels           : {labels_str}",
        f"  Headless         : {headless}",
        f"  Project dir      : {project_dir}",
        "=" * 72,
        "",
    ]
    print("\n".join(lines), flush=True)
