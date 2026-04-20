"""Contract every service performance module must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar


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
