"""CLI dispatcher — thin, dict-based routing to command handlers."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable

from ..errors import OsduPerfError
from ..telemetry import configure as configure_logging
from ._parser import build_parser
from .commands import init as init_cmd
from .commands import run_azure as run_azure_cmd
from .commands import run_local as run_local_cmd
from .commands import samples as samples_cmd
from .commands import validate as validate_cmd
from .commands import version as version_cmd

_Dispatch = Callable[[argparse.Namespace], int]


def _router(args: argparse.Namespace) -> _Dispatch:
    if args.command == "init":
        return init_cmd.run
    if args.command == "validate":
        return validate_cmd.run
    if args.command == "samples":
        return samples_cmd.run
    if args.command == "version":
        return version_cmd.run
    if args.command == "run":
        if args.target == "local":
            return run_local_cmd.run
        if args.target == "azure":
            return run_azure_cmd.run
    raise OsduPerfError(f"Unknown command '{args.command}'")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    configure_logging(level=level, verbose=args.verbose)

    try:
        handler = _router(args)
        return int(handler(args) or 0)
    except OsduPerfError as exc:
        if args.verbose:
            raise
        print(f"error: {exc}", file=sys.stderr)
        return 1


__all__ = ["main"]
