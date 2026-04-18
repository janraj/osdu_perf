"""Unit tests for the k8s manifest renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from osdu_perf.k8s.manifests import render_all, stage_build_context


def _values(**overrides: str) -> dict[str, str]:
    base = {
        "RUN_NAME": "scn-tn-pfx-260418000000",
        "NAMESPACE": "perf",
        "SERVICE_ACCOUNT": "osdu-perf-runner",
        "WORKLOAD_IDENTITY_CLIENT_ID": "11111111-2222-3333-4444-555555555555",
        "IMAGE": "myacr.azurecr.io/osdu-perf:abc123",
        "LOCUST_HOST": "https://example.osdu.test",
        "LOCUST_USERS": "5",
        "LOCUST_SPAWN_RATE": "1",
        "LOCUST_RUN_TIME": "60s",
        "LOCUST_EXPECT_WORKERS": "1",
        "ENGINE_INSTANCES": "2",
        "PARTITION": "dp1",
        "APPID": "abc-123",
        "SCENARIO": "search_query",
        "PROFILE_NAME": "U5_T60S",
        "TEST_NAME": "e2e",
        "WEB_UI": "false",
        "AZURE_CONFIG_PATH": "",
    }
    base.update(overrides)
    return base


def test_render_includes_namespace_configmap_and_master() -> None:
    out = render_all(_values(), worker_count=0)
    assert "kind: Namespace" in out
    assert "kind: ConfigMap" in out
    assert "kind: Service" in out
    assert "kind: Job" in out
    assert "osdu-perf.io/role: master" in out
    # No worker doc when worker_count == 0
    assert "osdu-perf.io/role: worker" not in out


def test_render_adds_worker_job_when_count_positive() -> None:
    out = render_all(_values(), worker_count=3)
    assert "osdu-perf.io/role: worker" in out
    assert "parallelism: 3" in out
    assert "completions: 3" in out


def test_render_substitutes_workload_identity_client_id() -> None:
    out = render_all(_values(WORKLOAD_IDENTITY_CLIENT_ID="cid-7"), worker_count=0)
    assert 'azure.workload.identity/client-id: "cid-7"' in out


def test_render_substitutes_image_and_run_name() -> None:
    out = render_all(_values(IMAGE="reg.io/test:v1", RUN_NAME="run-xyz"), worker_count=1)
    assert "reg.io/test:v1" in out
    assert "run-xyz-master" in out
    assert "run-xyz-workers" in out
    assert "run-xyz-master.perf.svc.cluster.local" in out


def test_render_raises_on_missing_value() -> None:
    incomplete = _values()
    incomplete.pop("LOCUST_HOST")
    with pytest.raises(KeyError):
        render_all(incomplete, worker_count=0)


def test_stage_build_context_writes_dockerfile_and_entrypoint(tmp_path: Path) -> None:
    stage_build_context(tmp_path, tmp_path)
    assert (tmp_path / "Dockerfile").is_file()
    assert (tmp_path / "_entrypoint.sh").is_file()
    assert (tmp_path / ".dockerignore").is_file()
    assert "FROM mcr.microsoft.com/azurelinux" in (tmp_path / "Dockerfile").read_text()
    assert "LOCUST_ROLE" in (tmp_path / "_entrypoint.sh").read_text()
