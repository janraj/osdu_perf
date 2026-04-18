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
    """Return the test_run_id_prefix as ``<test_name>-<configured_prefix>``.

    Precedence for the configured prefix: ``--test-run-id-prefix`` >
    ``run_scenario.test_run_id_prefix`` > ``"perf"``. The resolved test name
    (see :func:`resolved_test_name`) is always prepended so the prefix is
    self-describing in Kusto and downstream tooling.
    """
    cli = getattr(args, "test_run_id_prefix", None)
    base: str | None = None
    if cli:
        cleaned = str(cli).strip()
        if cleaned:
            base = cleaned
    if base is None:
        base = getattr(resolved, "test_run_id_prefix", None) or "perf"
    test_name = resolved_test_name(resolved, args)
    if base.startswith(f"{test_name}-") or base == test_name:
        return base
    return f"{test_name}-{base}"


def resolved_test_name(resolved, args: argparse.Namespace) -> str:
    """Return the stable ALT test-name component.

    Precedence: ``--test-name`` > ``run_scenario.test_name`` > scenario name.
    The ALT test id is built as ``<scenario>_<test_name>``; each run nests
    under this single test definition.
    """
    cli = getattr(args, "test_name", None)
    if cli:
        cleaned = str(cli).strip()
        if cleaned:
            return cleaned
    configured = getattr(resolved, "test_name", None)
    if configured:
        cleaned = str(configured).strip()
        if cleaned:
            return cleaned
    return resolved.scenario


def parse_label_overrides(args: argparse.Namespace) -> dict[str, str]:
    """Parse ``--label key=value`` flags into a dict.

    Raises ``ValueError`` on any malformed entry.
    """
    raw = getattr(args, "label", None) or []
    out: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(f"--label expects KEY=VALUE, got '{item}'.")
        key, _, value = item.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"--label has empty key: '{item}'.")
        out[key] = value
    return out


__all__ = [
    "apply_profile_overrides",
    "parse_label_overrides",
    "resolved_test_run_id_prefix",
]
