"""Dataclass models describing ``system_config.yaml`` and ``test_config.yaml``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OsduEnv:
    """OSDU instance coordinates from ``osdu_environment``."""

    host: str | None = None
    partition: str | None = None
    app_id: str | None = None


@dataclass(frozen=True)
class AzureLoadTestRef:
    """Pointer to an existing Azure Load Test resource."""

    name: str | None = None


@dataclass(frozen=True)
class KustoConfig:
    """Kusto (Azure Data Explorer) destination for test telemetry."""

    cluster_uri: str | None = None
    ingest_uri: str | None = None
    database: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.database and (self.cluster_uri or self.ingest_uri))


@dataclass(frozen=True)
class AzureInfra:
    """Azure infrastructure referenced by ``osdu_perf run azure``."""

    subscription_id: str | None = None
    resource_group: str | None = None
    location: str = "eastus"
    allow_resource_creation: bool = False
    azure_load_test: AzureLoadTestRef = field(default_factory=AzureLoadTestRef)
    kusto: KustoConfig = field(default_factory=KustoConfig)


@dataclass(frozen=True)
class TestMetadata:
    """Free-form labels applied to every Kusto telemetry row.

    ``performance_tier`` and ``version`` are conventional keys: the first
    selects a :class:`PerformanceProfile`; the second is a free-form tag.
    Any other keys are passed through verbatim.
    """

    performance_tier: str = "standard"
    version: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"performance_tier": self.performance_tier}
        if self.version is not None:
            data["version"] = self.version
        data.update(self.extras)
        return data


@dataclass(frozen=True)
class WaitTime:
    min: float = 1.0
    max: float = 3.0


@dataclass(frozen=True)
class TestDefaults:
    """Shared defaults used when a scenario omits a value."""

    users: int = 10
    spawn_rate: int = 2
    run_time: str = "60s"
    engine_instances: int = 1
    wait_time: WaitTime = field(default_factory=WaitTime)
    test_name_prefix: str = "osdu_perf_test"
    test_run_id_description: str = "Test run for OSDU APIs"


@dataclass(frozen=True)
class PerformanceProfile(TestDefaults):
    """Per-tier overrides of :class:`TestDefaults`."""


@dataclass(frozen=True)
class Scenario:
    """A named test scenario from ``test_config.yaml:scenarios``."""

    name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    """Top-level configuration tree."""

    osdu_env: OsduEnv
    azure_infra: AzureInfra
    test_metadata: TestMetadata
    defaults: TestDefaults
    profiles: dict[str, PerformanceProfile]
    scenarios: dict[str, Scenario]
    system_config_path: str | None = None
    test_config_path: str | None = None

    def scenario(self, name: str) -> Scenario:
        """Return the scenario by name, or raise ``ScenarioNotFoundError``."""
        from ..errors import ScenarioNotFoundError

        if name not in self.scenarios:
            available = ", ".join(sorted(self.scenarios)) or "(none configured)"
            raise ScenarioNotFoundError(
                f"Scenario '{name}' not found in test_config.yaml. "
                f"Available scenarios: {available}."
            )
        return self.scenarios[name]

    def profile(self, tier: str | None = None) -> PerformanceProfile:
        """Return the profile for ``tier`` (or the test_metadata tier)."""
        key = (tier or self.test_metadata.performance_tier or "standard").lower()
        return self.profiles.get(key, PerformanceProfile())

    def resolved_settings(self, scenario_name: str) -> TestDefaults:
        """Merge defaults → profile → scenario overrides into one view."""
        from dataclasses import replace

        merged = replace(self.defaults)
        profile = self.profile()
        merged = _merge_defaults(merged, profile)

        scenario = self.scenario(scenario_name)
        merged = _merge_mapping(merged, scenario.overrides)
        return merged


def _merge_defaults(base: TestDefaults, overlay: TestDefaults) -> TestDefaults:
    from dataclasses import replace

    return replace(
        base,
        users=overlay.users or base.users,
        spawn_rate=overlay.spawn_rate or base.spawn_rate,
        run_time=overlay.run_time or base.run_time,
        engine_instances=overlay.engine_instances or base.engine_instances,
        wait_time=overlay.wait_time or base.wait_time,
        test_name_prefix=overlay.test_name_prefix or base.test_name_prefix,
        test_run_id_description=overlay.test_run_id_description
        or base.test_run_id_description,
    )


def _merge_mapping(base: TestDefaults, overrides: dict[str, Any]) -> TestDefaults:
    from dataclasses import replace

    if not overrides:
        return base

    wait = base.wait_time
    if isinstance(overrides.get("wait_time"), dict):
        wait_overrides = overrides["wait_time"]
        wait = WaitTime(
            min=float(wait_overrides.get("min", wait.min)),
            max=float(wait_overrides.get("max", wait.max)),
        )

    return replace(
        base,
        users=int(overrides.get("users", base.users)),
        spawn_rate=int(overrides.get("spawn_rate", base.spawn_rate)),
        run_time=str(overrides.get("run_time", base.run_time)),
        engine_instances=int(overrides.get("engine_instances", base.engine_instances)),
        wait_time=wait,
        test_name_prefix=str(overrides.get("test_name_prefix", base.test_name_prefix)),
        test_run_id_description=str(
            overrides.get("test_run_id_description", base.test_run_id_description)
        ),
    )
