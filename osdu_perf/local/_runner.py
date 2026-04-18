"""Spawn Locust with the resolved OSDU configuration."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..config import AppConfig, PerformanceProfile
from ..errors import ConfigError
from ..telemetry import get_logger

_LOGGER = get_logger("local.runner")


@dataclass(frozen=True)
class LocalRunInputs:
    """Everything the local runner needs to invoke Locust."""

    host: str
    partition: str
    app_id: str
    bearer_token: str | None
    scenario: str
    profile: PerformanceProfile
    locustfile: Path
    headless: bool = False
    test_run_id_prefix: str = "perf"
    extra_labels: dict[str, str] = field(default_factory=dict)
    test_name: str | None = None
    profile_name: str | None = None
    run_id: str | None = None
    """Optional pre-computed run id. When ``None`` the runner generates
    one using :func:`build_run_id`. Passing it in lets the caller print
    a startup summary that references the same id the run uses."""


def build_run_id(inputs: LocalRunInputs) -> str:
    """Compute the run id for a local invocation (stable for its lifetime)."""
    return _run_id(inputs)


class LocalRunner:
    """Resolve a plan and invoke ``locust`` as a subprocess."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def run(self, inputs: LocalRunInputs) -> int:
        if not inputs.locustfile.exists():
            raise ConfigError(
                f"locustfile not found at '{inputs.locustfile}'. Run "
                f"'osdu_perf init --sample=<name>' to scaffold one."
            )

        env = os.environ.copy()
        env.update(
            {
                "HOST": inputs.host,
                "PARTITION": inputs.partition,
                "APPID": inputs.app_id,
                "TEST_RUN_ID": inputs.run_id or _run_id(inputs),
                "TEST_SCENARIO": inputs.scenario,
                "OSDU_PERF_PROFILE_NAME": inputs.profile_name or "",
                "OSDU_PERF_PROFILE_USERS": str(inputs.profile.users),
                "OSDU_PERF_PROFILE_SPAWN_RATE": str(inputs.profile.spawn_rate),
                "OSDU_PERF_PROFILE_RUN_TIME": str(inputs.profile.run_time),
                "OSDU_PERF_PROFILE_ENGINES": str(inputs.profile.engine_instances),
                "OSDU_PERF_TEST_NAME": inputs.test_name or "",
            }
        )
        if inputs.bearer_token:
            env["ADME_BEARER_TOKEN"] = inputs.bearer_token
        if inputs.extra_labels:
            import json

            env["OSDU_PERF_EXTRA_LABELS"] = json.dumps(inputs.extra_labels)

        command = _build_command(inputs)
        _LOGGER.info("Executing: %s", " ".join(command))
        try:
            return subprocess.run(command, env=env).returncode
        except FileNotFoundError as exc:
            raise ConfigError(
                "Locust is not installed. Run 'pip install osdu_perf[locust]' "
                "or 'pip install locust'."
            ) from exc


def _build_command(inputs: LocalRunInputs) -> list[str]:
    cmd = [
        "locust",
        "-f",
        str(inputs.locustfile),
        "--host",
        inputs.host,
        "--users",
        str(inputs.profile.users),
        "--spawn-rate",
        str(inputs.profile.spawn_rate),
        "--run-time",
        inputs.profile.run_time,
    ]
    if inputs.headless:
        cmd.append("--headless")
    return cmd


def _run_id(inputs: LocalRunInputs) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    prefix = (inputs.test_run_id_prefix or "perf").strip() or "perf"
    # Keep the legacy ``<scenario>_<prefix>_<ts>`` shape when no
    # ``test_name`` is configured. When it is (via
    # ``run_scenario.test_name`` or ``--test-name``), mirror the ALT
    # layout: ``<scenario>_<test_name>_<prefix>_<ts>``.
    name = (inputs.test_name or "").strip()
    if name and name != inputs.scenario:
        return f"{inputs.scenario}_{name}_{prefix}_{stamp}"
    return f"{inputs.scenario}_{prefix}_{stamp}"


__all__ = ["LocalRunner", "LocalRunInputs", "build_run_id"]
