"""Per-run state shared across Locust users.

:class:`RequestContext` is a small immutable carrier for the things every
user needs: OSDU coordinates, resolved auth header, and a correlation-id
generator. It replaces the 900-line ``InputHandler`` with a focused helper.
"""

from __future__ import annotations

import os
import secrets
import socket
import threading
from dataclasses import dataclass, field
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
    test_name: str = ""
    profile_name: str = ""
    profile_users: int = 0
    profile_spawn_rate: float = 0.0
    profile_run_time_seconds: int = 0
    profile_engine_instances: int = 0
    alt_test_run_id: str = ""
    engine_id: str = ""
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

        # Load-shape metadata -- set by the runners (local + ALT) so the
        # Kusto collector can emit first-class columns instead of stuffing
        # everything into the ``Labels`` dynamic bag.
        profile_name = os.getenv("OSDU_PERF_PROFILE_NAME", "")
        run_time_seconds = _parse_run_time(
            os.getenv("OSDU_PERF_PROFILE_RUN_TIME") or os.getenv("LOCUST_RUN_TIME") or ""
        )
        return cls(
            host=host,
            partition=partition,
            app_id=app_id,
            bearer_token=token,
            test_run_id=test_run_id,
            scenario=scenario,
            config=config,
            test_name=os.getenv("OSDU_PERF_TEST_NAME", "") or scenario,
            profile_name=profile_name,
            profile_users=_safe_int(
                os.getenv("OSDU_PERF_PROFILE_USERS") or os.getenv("LOCUST_USERS")
            ),
            profile_spawn_rate=_safe_float(
                os.getenv("OSDU_PERF_PROFILE_SPAWN_RATE") or os.getenv("LOCUST_SPAWN_RATE")
            ),
            profile_run_time_seconds=run_time_seconds,
            profile_engine_instances=_safe_int(os.getenv("OSDU_PERF_PROFILE_ENGINES")),
            alt_test_run_id=os.getenv("AZURE_LOAD_TEST_RUN_ID", ""),
            engine_id=os.getenv("WORKER_ID") or os.getenv("HOSTNAME") or _short_hostname(),
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

    def new_correlation_id(self, action: str = "") -> str:
        with self._lock:
            self._counter += 1
            counter = self._counter
        host4 = self._hostname[-4:] if len(self._hostname) > 4 else self._hostname
        if action:
            return f"{self.test_run_id}-{action}-{host4}-{counter}"
        return f"{self.test_run_id}-{host4}-{counter}"

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    def labels(self) -> dict[str, Any]:
        """Merged top-level ``labels`` + per-scenario ``metadata`` + CLI extras."""
        merged = dict(self.config.labels)
        default = self.config.scenario_defaults.get(self.scenario)
        if default is not None:
            merged.update(default.metadata)
        extra = os.getenv("OSDU_PERF_EXTRA_LABELS")
        if extra:
            try:
                import json

                parsed = json.loads(extra)
                if isinstance(parsed, dict):
                    merged.update({str(k): v for k, v in parsed.items()})
            except (ValueError, TypeError):
                pass
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
    """Build a unique test run id of the form
    ``<test_name>-<prefix>-<host4>-<rand8>``.

    - ``test_name`` comes from ``OSDU_PERF_TEST_NAME`` (falls back to
      ``scenario``).
    - ``prefix`` comes from ``OSDU_PERF_TEST_RUN_ID_PREFIX``, then
      ``config.test_run_id_prefix``, then ``"perf"``.
    - ``host4`` is the last 4 chars of the short hostname (Locust pod
      name suffix on AKS) so master/worker pods on the same run share a
      stable, identifiable suffix.
    - ``rand8`` is 8 hex chars from :mod:`secrets` — uniqueness across
      repeated runs (and across pods/cycles) without relying on clock
      precision.

    Generation is idempotent on the prefix: if the configured prefix
    already begins with ``<test_name>-`` (or equals it) it is not
    duplicated.
    """
    prefix = (
        (os.getenv("OSDU_PERF_TEST_RUN_ID_PREFIX") or "").strip()
        or getattr(config, "test_run_id_prefix", None)
        or "perf"
    )
    test_name = (os.getenv("OSDU_PERF_TEST_NAME") or "").strip() or scenario
    if prefix.startswith(f"{test_name}-") or prefix == test_name:
        head = prefix
    else:
        head = f"{test_name}-{prefix}"
    hostname = _short_hostname()
    host4 = hostname[-4:] if len(hostname) >= 4 else hostname
    rand8 = secrets.token_hex(4)  # 8 hex chars
    return f"{head}-{host4}-{rand8}"


def _safe_int(value: str | None) -> int:
    try:
        return int(float(value)) if value else 0
    except (TypeError, ValueError):
        return 0


def _safe_float(value: str | None) -> float:
    try:
        return float(value) if value else 0.0
    except (TypeError, ValueError):
        return 0.0


def _parse_run_time(value: str) -> int:
    """Parse Locust-style run time (``60s``/``15m``/``2h``) to seconds.

    When the value is already numeric (the ALT runner sends seconds)
    we use it directly.
    """
    if not value:
        return 0
    value = value.strip().lower()
    try:
        return int(float(value))
    except ValueError:
        pass
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    unit = value[-1]
    if unit in units:
        try:
            return int(float(value[:-1]) * units[unit])
        except ValueError:
            return 0
    return 0


__all__ = ["RequestContext"]
