"""Spawn Locust with the resolved OSDU configuration."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
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
                "TEST_RUN_ID": _run_id(inputs),
                "TEST_SCENARIO": inputs.scenario,
            }
        )
        if inputs.bearer_token:
            env["ADME_BEARER_TOKEN"] = inputs.bearer_token

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
    if inputs.scenario:
        cmd.extend(["--tags", inputs.scenario])
    if inputs.headless:
        cmd.append("--headless")
    return cmd


def _run_id(inputs: LocalRunInputs) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    prefix = inputs.test_run_id_prefix or "perf"
    return f"{inputs.scenario}_{prefix}_{stamp}"


__all__ = ["LocalRunner", "LocalRunInputs"]
