"""`osdu_perf validate`."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...config import load_config


def run(args: argparse.Namespace) -> int:
    project_dir = Path(args.directory).resolve()
    config = load_config(project_dir)
    env = config.osdu_env
    print("Configuration loaded successfully.")
    print(f"  host:      {env.host}")
    print(f"  partition: {env.partition}")
    print(f"  app_id:    {env.app_id}")
    print(f"  scenarios: {', '.join(sorted(config.scenarios)) or '<none>'}")
    return 0
