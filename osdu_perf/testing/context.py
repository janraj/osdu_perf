"""Per-run state shared across Locust users.

:class:`RequestContext` is a small immutable carrier for the things every
user needs: OSDU coordinates, resolved auth header, and a correlation-id
generator. It replaces the 900-line ``InputHandler`` with a focused helper.
"""

from __future__ import annotations

import os
import socket
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..auth import TokenProvider
from ..config import AppConfig
from ..errors import ConfigError


@dataclass
class RequestContext:
    """State shared by every Locust user in this process/engine."""

    host: str
    partition: str
    app_id: str
    bearer_token: str
    test_run_id: str
    scenario: str
    config: AppConfig
    _hostname: str = field(default_factory=lambda: _short_hostname())
    _counter: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _default_headers: dict[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._default_headers = {
            "Content-Type": "application/json",
            "data-partition-id": self.partition,
            "correlation-id": self.test_run_id,
            "Authorization": f"Bearer {self.bearer_token}",
        }

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------
    @classmethod
    def from_environment(cls, config: AppConfig, *, scenario: str) -> RequestContext:
        """Build a context from env vars (Azure Load Testing) or the AppConfig."""
        host = os.getenv("LOCUST_HOST") or config.osdu_env.host
        partition = os.getenv("PARTITION") or config.osdu_env.partition
        app_id = os.getenv("APPID") or config.osdu_env.app_id

        for value, name in (
            (host, "osdu_environment.host"),
            (partition, "osdu_environment.partition"),
            (app_id, "osdu_environment.app_id"),
        ):
            if not value:
                raise ConfigError(
                    f"Missing required value '{name}' in test_config.yaml "
                    f"or environment (LOCUST_HOST/PARTITION/APPID)."
                )

        token = TokenProvider().get_token(app_id)
        test_run_id = (
            os.getenv("TEST_RUN_ID_NAME")
            or os.getenv("TEST_RUN_ID")
            or _generate_test_run_id(config, scenario)
        )

        return cls(
            host=host,
            partition=partition,
            app_id=app_id,
            bearer_token=token,
            test_run_id=test_run_id,
            scenario=scenario,
            config=config,
        )

    # ------------------------------------------------------------------
    # Header helpers
    # ------------------------------------------------------------------
    @property
    def default_headers(self) -> dict[str, str]:
        return dict(self._default_headers)

    def request_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Return headers with a fresh correlation-id per request."""
        headers = dict(self._default_headers)
        headers["correlation-id"] = self.new_correlation_id()
        if extra:
            headers.update(extra)
        return headers

    def new_correlation_id(self) -> str:
        with self._lock:
            self._counter += 1
            counter = self._counter
        return f"{self.test_run_id}-{self._hostname}-{counter}"

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    def labels(self) -> dict[str, Any]:
        """Merged top-level ``labels`` + per-scenario ``metadata``."""
        merged = dict(self.config.labels)
        default = self.config.scenario_defaults.get(self.scenario)
        if default is not None:
            merged.update(default.metadata)
        return merged


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _short_hostname() -> str:
    try:
        raw = os.getenv("HOSTNAME") or socket.gethostname() or "unknown"
    except Exception:
        raw = "unknown"
    short = raw.split(".")[0]
    safe = "".join(ch for ch in short if ch.isalnum() or ch in "-_")
    return safe or "unknown"


def _generate_test_run_id(config: AppConfig, scenario: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    prefix = getattr(config, "test_run_id_prefix", None) or "perf"
    return f"{scenario}_{prefix}_{stamp}"


__all__ = ["RequestContext"]
