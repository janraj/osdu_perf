"""Typed configuration models and loader for ``osdu_perf``.

Users edit two YAML files in ``config/``:

* ``azure_config.yaml`` — Azure Load Test target + optional Kusto export sink
* ``test_config.yaml`` — OSDU environment, labels, profiles, scenario
  defaults, and the default ``run_scenario`` invocation

This package turns both into a single typed :class:`AppConfig` tree, which
is what every other subsystem consumes.
"""

from ._loader import load_config, load_from_paths
from ._models import (
    AksConfig,
    AksIngress,
    AppConfig,
    AzureLoadTest,
    ContainerRegistryConfig,
    KustoConfig,
    OsduEnv,
    PerformanceProfile,
    ResolvedRun,
    RunScenario,
    ScenarioDefault,
    WaitTime,
)

__all__ = [
    "AksConfig",
    "AksIngress",
    "AppConfig",
    "AzureLoadTest",
    "ContainerRegistryConfig",
    "KustoConfig",
    "OsduEnv",
    "PerformanceProfile",
    "ResolvedRun",
    "RunScenario",
    "ScenarioDefault",
    "WaitTime",
    "load_config",
    "load_from_paths",
]
