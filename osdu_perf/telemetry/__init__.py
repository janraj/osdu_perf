"""Centralized logging for the ``osdu_perf`` package."""

from __future__ import annotations

import logging
import sys

_DEFAULT_FORMAT = "[%(asctime)s %(name)s] %(levelname)s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_CONFIGURED = False


def configure(level: int = logging.INFO, *, verbose: bool = False) -> None:
    """Configure the ``osdu_perf`` root logger exactly once.

    Safe to call multiple times; subsequent calls only adjust the level.
    """
    global _CONFIGURED
    root = logging.getLogger("osdu_perf")
    effective_level = logging.DEBUG if verbose else level
    root.setLevel(effective_level)

    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, _DATE_FORMAT))
        root.addHandler(handler)
        root.propagate = False
        _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger named under the ``osdu_perf`` hierarchy."""
    if not name or name == "osdu_perf":
        return logging.getLogger("osdu_perf")
    return logging.getLogger(f"osdu_perf.{name}")


__all__ = ["configure", "get_logger"]
