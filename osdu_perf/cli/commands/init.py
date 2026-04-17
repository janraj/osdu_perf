"""`osdu_perf init` — scaffold a new test project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...scaffolding import Scaffolder, available_samples


def run(args: argparse.Namespace) -> int:
    if args.list_samples:
        for sample in available_samples():
            print(f"{sample.name:20}  {sample.title}")
        return 0

    target = Path(args.directory).resolve()
    scaffolder = Scaffolder(target, force=args.force)
    scaffolder.create(sample_name=args.sample)
    print(f"Scaffolded '{args.sample}' at {target}", file=sys.stderr)
    return 0
