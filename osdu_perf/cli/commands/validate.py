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
    print(f"  profiles:  {', '.join(sorted(config.profiles)) or '<none>'}")
    print(
        "  scenario defaults: "
        f"{', '.join(sorted(config.scenario_defaults)) or '<none>'}"
    )
    rs = config.run_scenario
    if rs.scenario:
        print(f"  run_scenario: {rs.scenario} (profile={rs.profile or '-'})")
    return 0
