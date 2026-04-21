"""Abstract base class for telemetry plugins."""

from abc import ABC, abstractmethod
from .report import TestReport


class TelemetryPlugin(ABC):
    """Interface that every telemetry backend must implement."""

    @abstractmethod
    def name(self) -> str:
        """Unique plugin name for logging/config (e.g., 'kusto', 'csv')."""
        ...

    @abstractmethod
    def is_enabled(self, config: dict) -> bool:
        """Return True if this plugin should run, based on metrics_collector config."""
        ...

    @abstractmethod
    def publish(self, report: TestReport) -> None:
        """Send the test report to the backend. Must not raise — log errors internally."""
        ...
