"""Shared helpers for ``run local`` / ``run azure`` command handlers."""

from __future__ import annotations

import argparse
from dataclasses import replace

from ...config import PerformanceProfile


def apply_profile_overrides(
    profile: PerformanceProfile,
    args: argparse.Namespace,
) -> PerformanceProfile:
    """Return ``profile`` with any non-None CLI overrides applied.

    Supported flags: ``--users``, ``--spawn-rate``, ``--run-time``,
    ``--engine-instances``.
    """
    overrides: dict[str, object] = {}
    if getattr(args, "users", None) is not None:
        overrides["users"] = args.users
    if getattr(args, "spawn_rate", None) is not None:
        overrides["spawn_rate"] = args.spawn_rate
    if getattr(args, "run_time", None) is not None:
        overrides["run_time"] = args.run_time
    if getattr(args, "engine_instances", None) is not None:
        overrides["engine_instances"] = args.engine_instances
    if not overrides:
        return profile
    return replace(profile, **overrides)


def resolved_test_run_id_prefix(resolved, args: argparse.Namespace) -> str:
    """Return the test_run_id_prefix, letting ``--test-run-id-prefix`` win."""
    cli = getattr(args, "test_run_id_prefix", None)
    if cli:
        cleaned = str(cli).strip()
        if cleaned:
            return cleaned
    return getattr(resolved, "test_run_id_prefix", None) or "perf"


__all__ = ["apply_profile_overrides", "resolved_test_run_id_prefix"]
