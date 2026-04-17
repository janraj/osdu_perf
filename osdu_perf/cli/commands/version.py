"""`osdu_perf version`."""

from __future__ import annotations

import argparse

from ..._version import __version__


def run(args: argparse.Namespace) -> int:
    print(__version__)
    return 0
