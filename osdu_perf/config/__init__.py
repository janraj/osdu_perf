"""Typed configuration models and loader for ``osdu_perf``.

Users edit two YAML files in ``config/``:

* ``system_config.yaml`` — environment, Azure infrastructure, Kusto telemetry
* ``test_config.yaml`` — scenarios and performance-tier profiles

This package turns both into a single typed :class:`AppConfig` tree, which
is what every other subsystem consumes.
"""

from ._loader import load_config, load_from_paths
from ._models import (
    AppConfig,
    AzureLoadTest,
    KustoConfig,
    OsduEnv,
    PerformanceProfile,
    Scenario,
    TestDefaults,
    TestMetadata,
    WaitTime,
)

__all__ = [
    "AppConfig",
    "AzureLoadTest",
    "KustoConfig",
    "OsduEnv",
    "PerformanceProfile",
    "Scenario",
    "TestDefaults",
    "TestMetadata",
    "WaitTime",
    "load_config",
    "load_from_paths",
]
