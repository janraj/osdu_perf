"""Telemetry package — plugin-based metrics collection for osdu_perf."""

from .plugin_base import TelemetryPlugin
from .dispatcher import TelemetryDispatcher
from .report import TestReport


def discover_plugins():
    """Return all available plugin instances.

    To add a new backend, import it here and append to the list.
    """
    from .plugins.kusto_plugin import KustoPlugin
    return [KustoPlugin()]


__all__ = [
    "TelemetryPlugin",
    "TelemetryDispatcher",
    "TestReport",
    "discover_plugins",
]
