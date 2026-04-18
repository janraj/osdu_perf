"""Unit tests for ContainerRegistryConfig and AksConfig parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from osdu_perf.config import load_from_paths


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_container_registry_defaults_when_missing(tmp_path: Path) -> None:
    azure = _write(tmp_path, "azure.yaml", "azure_load_test:\n  name: x\n")
    config = load_from_paths(azure, None)
    assert config.container_registry.is_configured is False
    assert config.container_registry.image_repository == "osdu-perf"


def test_container_registry_login_server_derived_from_name(tmp_path: Path) -> None:
    azure = _write(
        tmp_path,
        "azure.yaml",
        "aks:\n  container_registry:\n    name: myacr\n",
    )
    config = load_from_paths(azure, None)
    assert config.container_registry.name == "myacr"
    assert config.container_registry.login_server == "myacr.azurecr.io"
    assert config.container_registry.is_configured is True


def test_container_registry_explicit_login_server(tmp_path: Path) -> None:
    azure = _write(
        tmp_path,
        "azure.yaml",
        (
            "aks:\n"
            "  container_registry:\n"
            "    name: myacr\n"
            "    login_server: myacr.privatelink.azurecr.io\n"
            "    image_repository: perf/runner\n"
        ),
    )
    config = load_from_paths(azure, None)
    assert config.container_registry.login_server == "myacr.privatelink.azurecr.io"
    assert config.container_registry.image_repository == "perf/runner"


def test_aks_defaults_when_missing(tmp_path: Path) -> None:
    azure = _write(tmp_path, "azure.yaml", "azure_load_test:\n  name: x\n")
    config = load_from_paths(azure, None)
    assert config.aks.is_configured is False
    assert config.aks.namespace == "perf"
    assert config.aks.service_account == "osdu-perf-runner"
    assert config.aks.workload_identity_client_id is None


def test_aks_full(tmp_path: Path) -> None:
    azure = _write(
        tmp_path,
        "azure.yaml",
        (
            "aks:\n"
            "  subscription_id: sub-1\n"
            "  resource_group: rg-1\n"
            "  cluster_name: aks-1\n"
            "  namespace: perf-east\n"
            "  service_account: runner-sa\n"
            "  workload_identity_client_id: cid-7\n"
        ),
    )
    config = load_from_paths(azure, None)
    assert config.aks.is_configured is True
    assert config.aks.subscription_id == "sub-1"
    assert config.aks.resource_group == "rg-1"
    assert config.aks.cluster_name == "aks-1"
    assert config.aks.namespace == "perf-east"
    assert config.aks.service_account == "runner-sa"
    assert config.aks.workload_identity_client_id == "cid-7"


@pytest.mark.parametrize(
    "yaml_value,expected",
    [
        ("aks:\n  subscription_id: s\n  resource_group: r\n  cluster_name: c\n", True),
        ("aks:\n  subscription_id: s\n  resource_group: r\n", False),
        ("", False),
    ],
)
def test_aks_is_configured(tmp_path: Path, yaml_value: str, expected: bool) -> None:
    azure = _write(tmp_path, "azure.yaml", yaml_value or "x: 1\n")
    config = load_from_paths(azure, None)
    assert config.aks.is_configured is expected
