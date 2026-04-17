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
class TestMetadata:
    """Opaque labels applied verbatim to every Kusto telemetry row.

    The framework does not interpret any key. Add whatever makes your
    dashboards useful (``version``, ``build_id``, ``region``, etc.).
    """

    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.data)


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
    """Named settings bundle from ``test_config.yaml:profiles``."""


@dataclass(frozen=True)
class Scenario:
    """A named test scenario from ``test_config.yaml:scenarios``."""

    name: str
    profile: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    """Top-level configuration tree."""

    osdu_env: OsduEnv
    azure_load_test: AzureLoadTest
    kusto_export: KustoConfig
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

    def profile(self, name: str | None = None) -> PerformanceProfile | None:
        """Return the named profile, the ``default`` profile, or ``None``.

        Explicit ``name`` is required to exist. Otherwise returns the
        ``default`` profile if defined, else ``None`` (caller should
        treat this as "no profile layer, use raw :class:`TestDefaults`").
        """
        if name:
            key = name.lower()
            if key not in self.profiles:
                from ..errors import ConfigError

                available = ", ".join(sorted(self.profiles)) or "(none configured)"
                raise ConfigError(
                    f"Profile '{name}' not found in test_config.yaml. "
                    f"Available profiles: {available}."
                )
            return self.profiles[key]
        return self.profiles.get("default")

    def resolved_settings(
        self,
        scenario_name: str,
        profile_name: str | None = None,
    ) -> TestDefaults:
        """Merge defaults → profile → scenario overrides into one view.

        Profile resolution order: ``profile_name`` arg wins, then the
        scenario's own ``profile:`` field, then the ``default`` profile
        if defined, otherwise no profile layer is applied.
        """
        from dataclasses import replace

        scenario = self.scenario(scenario_name)
        effective_profile = profile_name or scenario.profile
        profile = self.profile(effective_profile)

        merged = replace(self.defaults)
        if profile is not None:
            merged = _merge_defaults(merged, profile)
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
