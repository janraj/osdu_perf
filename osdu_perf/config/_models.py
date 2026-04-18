"""Dataclass models describing ``azure_config.yaml`` and ``test_config.yaml``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ----------------------------------------------------------------------
# azure_config.yaml
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class AzureLoadTest:
    """Azure Load Testing resource coordinates (used by ``run azure`` only)."""

    subscription_id: str | None = None
    resource_group: str | None = None
    location: str = "eastus"
    allow_resource_creation: bool = False
    name: str | None = None


@dataclass(frozen=True)
class KustoConfig:
    """Kusto (Azure Data Explorer) destination for test telemetry.

    Applies to both ``run local`` and ``run azure``. When configured,
    every completed Locust run ingests a summary row into the configured
    database.
    """

    cluster_uri: str | None = None
    ingest_uri: str | None = None
    database: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.database and (self.cluster_uri or self.ingest_uri))


@dataclass(frozen=True)
class ContainerRegistryConfig:
    """Azure Container Registry coordinates (used by ``run k8s`` only).

    ``login_server`` is the fully-qualified ACR hostname (``<name>.azurecr.io``);
    ``name`` is the short ACR resource name used by ``az acr login``.
    ``image_repository`` is the repo path within the registry where the
    test image is pushed (default: ``osdu-perf``).
    """

    login_server: str | None = None
    name: str | None = None
    image_repository: str = "osdu-perf"

    @property
    def is_configured(self) -> bool:
        return bool(self.login_server and self.name)


@dataclass(frozen=True)
class AksConfig:
    """AKS cluster coordinates (used by ``run k8s`` only).

    The runner shells out to ``az aks get-credentials`` to merge the
    cluster context into ``kubectl`` before applying manifests.
    ``workload_identity_client_id`` is the AAD app/UAMI client id that the
    pod's ServiceAccount is federated to; both OSDU and Kusto auth in the
    pod resolve through this identity.
    """

    subscription_id: str | None = None
    resource_group: str | None = None
    cluster_name: str | None = None
    namespace: str = "perf"
    service_account: str = "osdu-perf-runner"
    workload_identity_client_id: str | None = None
    web_ui: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.subscription_id and self.resource_group and self.cluster_name)


# ----------------------------------------------------------------------
# test_config.yaml
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class OsduEnv:
    """OSDU instance coordinates from ``osdu_environment``."""

    host: str | None = None
    partition: str | None = None
    app_id: str | None = None


@dataclass(frozen=True)
class WaitTime:
    """Locust ``wait_time`` bounds in seconds."""

    min: float = 1.0
    max: float = 3.0


@dataclass(frozen=True)
class PerformanceProfile:
    """A named load shape from ``profiles:``.

    The canonical naming convention is ``U<users>_T<duration>`` (e.g.
    ``U100_T15M``), but any key works — the string is opaque to the
    framework.
    """

    users: int = 10
    spawn_rate: int = 2
    run_time: str = "60s"
    engine_instances: int = 1
    wait_time: WaitTime = field(default_factory=WaitTime)


@dataclass(frozen=True)
class ScenarioDefault:
    """Per-scenario default profile + metadata from ``scenario_defaults:``."""

    profile: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunScenario:
    """The default ``osdu_perf run`` invocation from ``run_scenario:``.

    Used only when the CLI omits ``--scenario``. Fields inside apply
    *only* when this block supplied the scenario.
    """

    scenario: str | None = None
    profile: str | None = None
    test_name: str | None = None
    test_run_id_prefix: str | None = None
    labels: dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------
# Root
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class AppConfig:
    """Top-level configuration tree."""

    osdu_env: OsduEnv
    azure_load_test: AzureLoadTest
    kusto_export: KustoConfig
    container_registry: ContainerRegistryConfig
    aks: AksConfig
    labels: dict[str, Any]
    profiles: dict[str, PerformanceProfile]
    scenario_defaults: dict[str, ScenarioDefault]
    run_scenario: RunScenario
    test_run_id_prefix: str = "perf"
    azure_config_path: str | None = None
    test_config_path: str | None = None

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def resolve(
        self,
        scenario: str | None = None,
        profile: str | None = None,
    ) -> ResolvedRun:
        """Pick the scenario + profile + labels for a single run.

        Precedence:

        * **scenario**: ``scenario`` arg > ``run_scenario.scenario`` > error.
        * **profile**: ``profile`` arg > (if scenario came from
          ``run_scenario``) ``run_scenario.profile`` >
          ``scenario_defaults[scenario].profile`` > error.
        * **labels**: top-level ``labels`` merged with
          ``scenario_defaults[scenario].metadata`` merged with (when
          scenario came from ``run_scenario``) ``run_scenario.labels``.
        """
        from ..errors import ConfigError, ScenarioNotFoundError

        used_run_scenario = scenario is None
        effective_scenario = scenario or self.run_scenario.scenario
        if not effective_scenario:
            raise ScenarioNotFoundError(
                "No scenario specified. Pass --scenario or set "
                "'run_scenario.scenario' in test_config.yaml."
            )

        default = self.scenario_defaults.get(effective_scenario)

        if profile:
            profile_name = profile
        elif used_run_scenario and self.run_scenario.profile:
            profile_name = self.run_scenario.profile
        elif default is not None:
            profile_name = default.profile
        else:
            available = ", ".join(sorted(self.profiles)) or "(none configured)"
            raise ConfigError(
                f"No profile resolved for scenario '{effective_scenario}'. "
                f"Pass --profile, or add a 'scenario_defaults.{effective_scenario}.profile' "
                f"entry. Available profiles: {available}."
            )

        key = profile_name.lower()
        if key not in self.profiles:
            available = ", ".join(sorted(self.profiles)) or "(none configured)"
            raise ConfigError(
                f"Profile '{profile_name}' not found in test_config.yaml. "
                f"Available profiles: {available}."
            )

        merged_labels: dict[str, Any] = dict(self.labels)
        if default is not None:
            merged_labels.update(default.metadata)
        if used_run_scenario:
            merged_labels.update(self.run_scenario.labels)

        return ResolvedRun(
            scenario=effective_scenario,
            profile_name=profile_name,
            profile=self.profiles[key],
            labels=merged_labels,
            test_run_id_prefix=self.test_run_id_prefix,
            test_name=(self.run_scenario.test_name if used_run_scenario else None),
        )


@dataclass(frozen=True)
class ResolvedRun:
    """Outcome of :meth:`AppConfig.resolve` — everything one run needs."""

    scenario: str
    profile_name: str
    profile: PerformanceProfile
    labels: dict[str, Any]
    test_run_id_prefix: str = "perf"
    test_name: str | None = None


__all__ = [
    "AksConfig",
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
]
