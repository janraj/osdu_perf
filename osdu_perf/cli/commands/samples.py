"""`osdu_perf samples`."""

from __future__ import annotations

import argparse

from ...scaffolding import available_samples


def run(args: argparse.Namespace) -> int:
    for sample in available_samples():
        print(f"{sample.name:20}  {sample.title}")
    return 0
