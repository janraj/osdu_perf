"""Contract every service performance module must implement."""

from __future__ import annotations

import socket
import threading
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar


def _short_hostname() -> str:
    try:
        raw = (socket.gethostname() or "unknown").split(".")[0]
    except Exception:
        raw = "unknown"
    return "".join(ch for ch in raw if ch.isalnum() or ch in "-_") or "unknown"


class BaseService(ABC):
    """Base class for a test-service that exercises one OSDU API surface."""

    # Optional human-friendly identifier for dashboards. When a subclass
    # sets this class attribute (``service_name = "search"``), every row
    # the service emits to ``LocustMetricsV2``/``LocustExceptionsV2``
    # will use it as the ``Service`` column. When unset we derive it
    # from the URL path (``/api/<service>/...``) or fall back to the
    # scenario name.
    service_name: ClassVar[str | None] = None

    def __init__(self, client: Any = None) -> None:
        self.client = client
        self.test_run_id: str = ""
        self._hostname: str = _short_hostname()
        self._counter: int = 0
        self._lock: threading.Lock = threading.Lock()

    def new_correlation_id(self, action: str = "") -> str:
        """Generate a correlation-id: <testRunId>-<action>-<host4>-<counter>."""
        with self._lock:
            self._counter += 1
            counter = self._counter
        host4 = self._hostname[-4:] if len(self._hostname) > 4 else self._hostname
        if self.test_run_id:
            if action:
                return f"{self.test_run_id}-{action}-{host4}-{counter}"
            return f"{self.test_run_id}-{host4}-{counter}"
        if action:
            return f"{action}-{host4}-{counter}"
        return f"{host4}-{counter}"

    @abstractmethod
    def execute(
        self,
        headers: Mapping[str, str] | None = None,
        partition: str | None = None,
        host: str | None = None,
    ) -> None:
        """Run all service-specific tasks (called from a Locust ``@task``)."""

    @abstractmethod
    def provide_explicit_token(self) -> str:
        """Return a bearer token to use instead of the shared user token."""

    @abstractmethod
    def prehook(
        self,
        headers: Mapping[str, str] | None = None,
        partition: str | None = None,
        host: str | None = None,
    ) -> None:
        """Pre-test setup invoked once per user start."""

    @abstractmethod
    def posthook(
        self,
        headers: Mapping[str, str] | None = None,
        partition: str | None = None,
        host: str | None = None,
    ) -> None:
        """Post-test cleanup invoked once per user stop."""


__all__ = ["BaseService"]
