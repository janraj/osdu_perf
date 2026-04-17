"""Config file discovery + parsing.

The loader looks for ``config/system_config.yaml`` and
``config/test_config.yaml`` starting at ``cwd`` and walking up the
directory tree. Explicit paths may also be supplied.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from ..errors import ConfigError
from ._models import (
    AppConfig,
    AzureInfra,
    AzureLoadTestRef,
    KustoConfig,
    OsduEnv,
    PerformanceProfile,
    Scenario,
    TestDefaults,
    TestMetadata,
    WaitTime,
)

_SYSTEM_FILENAME = "system_config.yaml"
_TEST_FILENAME = "test_config.yaml"


def load_config(search_root: Path | None = None) -> AppConfig:
    """Discover and load config files starting from ``search_root`` (or cwd)."""
    root = Path(search_root or Path.cwd())
    system_path, test_path = _discover(root)
    return load_from_paths(system_path, test_path)


def load_from_paths(
    system_config_path: Path | None,
    test_config_path: Path | None,
) -> AppConfig:
    """Load configuration from explicit file paths (either may be ``None``)."""
    system = _read_yaml(system_config_path) if system_config_path else {}
    test = _read_yaml(test_config_path) if test_config_path else {}

    return AppConfig(
        osdu_env=_parse_osdu_env(test),
        azure_infra=_parse_azure_infra(system),
        test_metadata=_parse_test_metadata(test),
        defaults=_parse_defaults(test),
        profiles=_parse_profiles(test),
        scenarios=_parse_scenarios(test),
        system_config_path=str(system_config_path) if system_config_path else None,
        test_config_path=str(test_config_path) if test_config_path else None,
    )


def _discover(start: Path) -> tuple[Path | None, Path | None]:
    system_path: Path | None = None
    test_path: Path | None = None
    for directory in (start, *start.parents):
        if system_path is None:
            system_path = _first_existing(
                directory / "config" / _SYSTEM_FILENAME,
                directory / _SYSTEM_FILENAME,
            )
        if test_path is None:
            test_path = _first_existing(
                directory / "config" / _TEST_FILENAME,
                directory / _TEST_FILENAME,
            )
        if system_path and test_path:
            break
    return system_path, test_path


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


def _parse_osdu_env(test: dict[str, Any]) -> OsduEnv:
    section = test.get("osdu_environment") or {}
    return OsduEnv(
        host=_clean_str(section.get("host")),
        partition=_clean_str(section.get("partition")),
        app_id=_clean_str(section.get("app_id")),
    )


def _parse_azure_infra(system: dict[str, Any]) -> AzureInfra:
    section = system.get("azure_infra") or {}
    alt = section.get("azure_load_test") or {}
    kusto = section.get("kusto") or {}

    cluster_uri = _clean_str(kusto.get("cluster_uri"))
    ingest_uri = _clean_str(kusto.get("ingest_uri"))
    if cluster_uri and not ingest_uri:
        ingest_uri = _ingest_from_cluster(cluster_uri)
    elif ingest_uri and not cluster_uri:
        cluster_uri = _cluster_from_ingest(ingest_uri)

    return AzureInfra(
        subscription_id=_clean_str(section.get("subscription_id")),
        resource_group=_clean_str(section.get("resource_group")),
        location=_clean_str(section.get("location")) or "eastus",
        allow_resource_creation=_as_bool(section.get("allow_resource_creation", False)),
        azure_load_test=AzureLoadTestRef(name=_clean_str(alt.get("name"))),
        kusto=KustoConfig(
            cluster_uri=cluster_uri,
            ingest_uri=ingest_uri,
            database=_clean_str(kusto.get("database")),
        ),
    )


def _parse_test_metadata(test: dict[str, Any]) -> TestMetadata:
    section = test.get("test_metadata") or {}
    if not isinstance(section, dict):
        return TestMetadata()
    return TestMetadata(data=dict(section))


def _parse_defaults(test: dict[str, Any]) -> TestDefaults:
    section = test.get("test_settings") or {}
    return _defaults_from_mapping(section, TestDefaults())


def _parse_profiles(test: dict[str, Any]) -> dict[str, PerformanceProfile]:
    section = test.get("profiles") or {}
    if not isinstance(section, dict):
        return {}
    profiles: dict[str, PerformanceProfile] = {}
    for raw_name, mapping in section.items():
        if not isinstance(mapping, dict):
            continue
        base = _defaults_from_mapping(mapping, TestDefaults())
        profiles[str(raw_name).lower()] = PerformanceProfile(
            users=base.users,
            spawn_rate=base.spawn_rate,
            run_time=base.run_time,
            engine_instances=base.engine_instances,
            wait_time=base.wait_time,
            test_name_prefix=base.test_name_prefix,
            test_run_id_description=base.test_run_id_description,
        )
    return profiles


def _parse_scenarios(test: dict[str, Any]) -> dict[str, Scenario]:
    section = test.get("scenarios") or {}
    if not isinstance(section, dict):
        return {}
    scenarios: dict[str, Scenario] = {}
    for name, body in section.items():
        body = body or {}
        if not isinstance(body, dict):
            continue
        metadata = dict(body.get("metadata") or {})
        profile = _clean_str(body.get("profile"))
        overrides = {
            k: v
            for k, v in body.items()
            if k not in {"metadata", "profile"}
        }
        scenarios[str(name)] = Scenario(
            name=str(name),
            profile=profile,
            metadata=metadata,
            overrides=overrides,
        )
    return scenarios


def _defaults_from_mapping(mapping: dict[str, Any], base: TestDefaults) -> TestDefaults:
    wait = base.wait_time
    wait_src = mapping.get("default_wait_time") or mapping.get("wait_time")
    if isinstance(wait_src, dict):
        wait = WaitTime(
            min=float(wait_src.get("min", wait.min)),
            max=float(wait_src.get("max", wait.max)),
        )
    return replace(
        base,
        users=int(mapping.get("users", base.users)),
        spawn_rate=int(mapping.get("spawn_rate", base.spawn_rate)),
        run_time=str(mapping.get("run_time", base.run_time)),
        engine_instances=int(mapping.get("engine_instances", base.engine_instances)),
        wait_time=wait,
        test_name_prefix=str(mapping.get("test_name_prefix", base.test_name_prefix)),
        test_run_id_description=str(
            mapping.get("test_run_id_description", base.test_run_id_description)
        ),
    )


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
        host = host[len("ingest-"):]
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
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "on"}
    return bool(value)
