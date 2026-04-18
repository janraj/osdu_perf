"""Config file discovery + parsing.

The loader looks for ``config/azure_config.yaml`` and
``config/test_config.yaml`` starting at ``cwd`` and walking up the
directory tree. Explicit paths may also be supplied.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ..errors import ConfigError
from ..telemetry import get_logger
from ._models import (
    AksConfig,
    AppConfig,
    AzureLoadTest,
    ContainerRegistryConfig,
    KustoConfig,
    OsduEnv,
    PerformanceProfile,
    RunScenario,
    ScenarioDefault,
    WaitTime,
)

_AZURE_FILENAME = "azure_config.yaml"
_TEST_FILENAME = "test_config.yaml"
_LOGGER = get_logger("config.loader")


def load_config(search_root: Path | None = None) -> AppConfig:
    """Discover and load config files starting from ``search_root`` (or cwd).

    If the ``OSDU_PERF_AZURE_CONFIG`` environment variable is set, it takes
    priority over discovery for the azure_config.yaml file (resolved relative
    to ``search_root`` if not absolute). The pod-side runtime uses this so the
    same image can target different clusters by env-var injection.
    """
    root = Path(search_root or Path.cwd())
    azure_path, test_path = _discover(root)
    env_override = os.getenv("OSDU_PERF_AZURE_CONFIG", "").strip()
    if env_override:
        candidate = Path(env_override)
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists():
            azure_path = candidate
        else:
            _LOGGER.warning(
                "OSDU_PERF_AZURE_CONFIG=%s does not exist; falling back to %s",
                env_override,
                azure_path,
            )
    return load_from_paths(azure_path, test_path)


def load_from_paths(
    azure_config_path: Path | None,
    test_config_path: Path | None,
) -> AppConfig:
    """Load configuration from explicit file paths (either may be ``None``)."""
    azure = _read_yaml(azure_config_path) if azure_config_path else {}
    test = _read_yaml(test_config_path) if test_config_path else {}

    run_scenario_block = test.get("run_scenario") or {}
    if not isinstance(run_scenario_block, dict):
        run_scenario_block = {}
    run_scenario_prefix = _clean_str(run_scenario_block.get("test_run_id_prefix"))
    top_level_prefix = _clean_str(test.get("test_run_id_prefix"))
    if top_level_prefix and not run_scenario_prefix:
        _LOGGER.warning(
            "Top-level 'test_run_id_prefix' is deprecated; move it under "
            "'run_scenario.test_run_id_prefix' in test_config.yaml."
        )

    return AppConfig(
        osdu_env=_parse_osdu_env(test),
        azure_load_test=_parse_azure_load_test(azure),
        kusto_export=_parse_kusto_export(azure),
        container_registry=_parse_container_registry(azure),
        aks=_parse_aks(azure),
        labels=_parse_labels(test),
        profiles=_parse_profiles(test),
        scenario_defaults=_parse_scenario_defaults(test),
        run_scenario=_parse_run_scenario(test),
        test_run_id_prefix=run_scenario_prefix or top_level_prefix or "perf",
        azure_config_path=str(azure_config_path) if azure_config_path else None,
        test_config_path=str(test_config_path) if test_config_path else None,
    )


# ----------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------
def _discover(start: Path) -> tuple[Path | None, Path | None]:
    azure_path: Path | None = None
    test_path: Path | None = None
    for directory in (start, *start.parents):
        if azure_path is None:
            azure_path = _first_existing(
                directory / "config" / _AZURE_FILENAME,
                directory / _AZURE_FILENAME,
            )
        if test_path is None:
            test_path = _first_existing(
                directory / "config" / _TEST_FILENAME,
                directory / _TEST_FILENAME,
            )
        if azure_path and test_path:
            break
    return azure_path, test_path


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            content = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Cannot read {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise ConfigError(f"Top-level of {path} must be a mapping")
    return content


# ----------------------------------------------------------------------
# azure_config.yaml parsing
# ----------------------------------------------------------------------
def _parse_azure_load_test(azure: dict[str, Any]) -> AzureLoadTest:
    section = azure.get("azure_load_test") or {}
    if not isinstance(section, dict):
        return AzureLoadTest()
    return AzureLoadTest(
        subscription_id=_clean_str(section.get("subscription_id")),
        resource_group=_clean_str(section.get("resource_group")),
        location=_clean_str(section.get("location")) or "eastus",
        allow_resource_creation=_as_bool(section.get("allow_resource_creation", False)),
        name=_clean_str(section.get("name")),
    )


def _parse_kusto_export(azure: dict[str, Any]) -> KustoConfig:
    section = azure.get("kusto_export") or {}
    if not isinstance(section, dict):
        return KustoConfig()
    cluster_uri = _clean_str(section.get("cluster_uri"))
    ingest_uri = _clean_str(section.get("ingest_uri"))
    if cluster_uri and not ingest_uri:
        ingest_uri = _ingest_from_cluster(cluster_uri)
    elif ingest_uri and not cluster_uri:
        cluster_uri = _cluster_from_ingest(ingest_uri)
    return KustoConfig(
        cluster_uri=cluster_uri,
        ingest_uri=ingest_uri,
        database=_clean_str(section.get("database")),
    )


def _parse_container_registry(azure: dict[str, Any]) -> ContainerRegistryConfig:
    aks_section = azure.get("aks") or {}
    section = aks_section.get("container_registry") if isinstance(aks_section, dict) else None
    if not isinstance(section, dict):
        return ContainerRegistryConfig()
    name = _clean_str(section.get("name"))
    login_server = _clean_str(section.get("login_server"))
    if name and not login_server:
        login_server = f"{name}.azurecr.io"
    return ContainerRegistryConfig(
        login_server=login_server,
        name=name,
        image_repository=_clean_str(section.get("image_repository")) or "osdu-perf",
    )


def _parse_aks(azure: dict[str, Any]) -> AksConfig:
    section = azure.get("aks") or {}
    if not isinstance(section, dict):
        return AksConfig()
    return AksConfig(
        subscription_id=_clean_str(section.get("subscription_id")),
        resource_group=_clean_str(section.get("resource_group")),
        cluster_name=_clean_str(section.get("cluster_name")),
        namespace=_clean_str(section.get("namespace")) or "perf",
        service_account=_clean_str(section.get("service_account")) or "osdu-perf-runner",
        workload_identity_client_id=_clean_str(section.get("workload_identity_client_id")),
        web_ui=_as_bool(section.get("web_ui", False)),
    )


# ----------------------------------------------------------------------
# test_config.yaml parsing
# ----------------------------------------------------------------------
def _parse_osdu_env(test: dict[str, Any]) -> OsduEnv:
    section = test.get("osdu_environment") or {}
    return OsduEnv(
        host=_clean_str(section.get("host")),
        partition=_clean_str(section.get("partition")),
        app_id=_clean_str(section.get("app_id")),
    )


def _parse_labels(test: dict[str, Any]) -> dict[str, Any]:
    section = test.get("labels") or {}
    if not isinstance(section, dict):
        return {}
    return dict(section)


def _parse_profiles(test: dict[str, Any]) -> dict[str, PerformanceProfile]:
    section = test.get("profiles") or {}
    if not isinstance(section, dict):
        return {}
    profiles: dict[str, PerformanceProfile] = {}
    for raw_name, mapping in section.items():
        if not isinstance(mapping, dict):
            continue
        wait_src = mapping.get("wait_time") or mapping.get("default_wait_time")
        wait = WaitTime()
        if isinstance(wait_src, dict):
            wait = WaitTime(
                min=float(wait_src.get("min", wait.min)),
                max=float(wait_src.get("max", wait.max)),
            )
        profiles[str(raw_name).lower()] = PerformanceProfile(
            users=int(mapping.get("users", 10)),
            spawn_rate=int(mapping.get("spawn_rate", 2)),
            run_time=str(mapping.get("run_time", "60s")),
            engine_instances=int(mapping.get("engine_instances", 1)),
            wait_time=wait,
        )
    return profiles


def _parse_scenario_defaults(test: dict[str, Any]) -> dict[str, ScenarioDefault]:
    section = test.get("scenario_defaults") or {}
    if not isinstance(section, dict):
        return {}
    out: dict[str, ScenarioDefault] = {}
    for name, body in section.items():
        body = body or {}
        if not isinstance(body, dict):
            continue
        profile = _clean_str(body.get("profile"))
        if not profile:
            raise ConfigError(
                f"scenario_defaults.{name}.profile is required "
                f"(must reference a key under 'profiles:')."
            )
        metadata = body.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        out[str(name)] = ScenarioDefault(profile=profile, metadata=dict(metadata))
    return out


def _parse_run_scenario(test: dict[str, Any]) -> RunScenario:
    section = test.get("run_scenario") or {}
    if not isinstance(section, dict):
        return RunScenario()
    labels = section.get("labels") or {}
    if not isinstance(labels, dict):
        labels = {}
    return RunScenario(
        scenario=_clean_str(section.get("scenario")),
        profile=_clean_str(section.get("profile")),
        test_name=_clean_str(section.get("test_name")),
        test_run_id_prefix=_clean_str(section.get("test_run_id_prefix")),
        labels=dict(labels),
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _ingest_from_cluster(uri: str) -> str | None:
    scheme, rest = _split_scheme(uri)
    host, _, path = rest.partition("/")
    if not host:
        return None
    prefixed = host if host.startswith("ingest-") else f"ingest-{host}"
    return f"{scheme}://{prefixed}" + (f"/{path}" if path else "")


def _cluster_from_ingest(uri: str) -> str | None:
    scheme, rest = _split_scheme(uri)
    host, _, path = rest.partition("/")
    if host.startswith("ingest-"):
        host = host[len("ingest-") :]
    return f"{scheme}://{host}" + (f"/{path}" if path else "")


def _split_scheme(uri: str) -> tuple[str, str]:
    try:
        scheme, rest = uri.split("://", 1)
        return scheme, rest
    except ValueError:
        return "https", uri


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "on"}


__all__ = ["load_config", "load_from_paths"]
