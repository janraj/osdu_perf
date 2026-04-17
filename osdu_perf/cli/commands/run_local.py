"""`osdu_perf run local`."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...auth import TokenProvider
from ...config import load_config
from ...errors import ConfigError
from ...local import LocalRunInputs, LocalRunner


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
    bearer = args.bearer_token or TokenProvider(explicit_token=args.bearer_token).get_token(app_id)

    inputs = LocalRunInputs(
        host=host,
        partition=partition,
        app_id=app_id,
        bearer_token=bearer,
        scenario=resolved.scenario,
        profile=resolved.profile,
        locustfile=project_dir / "locustfile.py",
        headless=args.headless,
    )
    return LocalRunner(config).run(inputs)
