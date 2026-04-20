"""Unit tests for the bundled Helm chart + values dict rendering."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from osdu_perf.config import (
    AksConfig,
    AksIngress,
    AppConfig,
    AzureLoadTest,
    ContainerRegistryConfig,
    KustoConfig,
    OsduEnv,
    PerformanceProfile,
    RunScenario,
)
from osdu_perf.k8s.runner import K8sRunInputs, K8sRunner, _chart_path


def _app_config(ingress: AksIngress | None = None) -> AppConfig:
    return AppConfig(
        osdu_env=OsduEnv(host="https://h", partition="dp1", app_id="app-id"),
        azure_load_test=AzureLoadTest(),
        kusto_export=KustoConfig(),
        aks=AksConfig(
            subscription_id="sub-guid",
            resource_group="rg",
            cluster_name="aks",
            namespace="perf",
            service_account="osdu-perf-runner",
            workload_identity_client_id="cid",
            ingress=ingress or AksIngress(),
        ),
        container_registry=ContainerRegistryConfig(
            name="myacr",
            login_server="myacr.azurecr.io",
            image_repository="osdu-perf",
        ),
        labels={},
        profiles={},
        scenario_defaults={},
        run_scenario=RunScenario(),
    )


def _inputs(**over) -> K8sRunInputs:
    defaults = dict(
        host="https://h",
        partition="dp1",
        app_id="app-id",
        test_directory=Path("."),
        profile=PerformanceProfile(
            users=10, spawn_rate=2, run_time="60s", engine_instances=3
        ),
        labels={"sku": "flex"},
        scenario="search_query",
        test_name="e2e",
        profile_name="U10_T60S",
    )
    defaults.update(over)
    return K8sRunInputs(**defaults)


def test_build_values_headless_computes_worker_count_and_propagates_labels():
    runner = K8sRunner(_app_config())
    values = runner._build_values(
        inputs=_inputs(),
        run_name="scn-tn-pfx-260418000000",
        namespace="perf",
        image_ref="myacr.azurecr.io/osdu-perf:abc",
    )

    assert values["workers"]["count"] == 2
    assert values["mode"] == "headless"
    assert values["image"] == {
        "repository": "myacr.azurecr.io/osdu-perf",
        "tag": "abc",
        "pullPolicy": "Always",
    }
    assert values["env"]["OSDU_PERF_EXTRA_LABELS"] == '{"sku":"flex"}'
    assert values["env"]["LOCUST_EXPECT_WORKERS"] == "2"
    assert values["env"]["OSDU_PERF_PROFILE_ENGINES"] == "3"
    assert values["ingress"]["type"] == "none"


def test_build_values_webui_switches_mode():
    runner = K8sRunner(_app_config())
    values = runner._build_values(
        inputs=_inputs(web_ui=True),
        run_name="r",
        namespace="perf",
        image_ref="myacr.azurecr.io/osdu-perf:abc",
    )
    assert values["mode"] == "webui"
    assert values["env"]["WEB_UI"] == "true"


def test_build_values_serviceaccount_create_default_false():
    runner = K8sRunner(_app_config())
    values = runner._build_values(
        inputs=_inputs(),
        run_name="r",
        namespace="perf",
        image_ref="myacr.azurecr.io/osdu-perf:abc",
    )
    assert values["serviceAccount"]["create"] is False
    assert values["serviceAccount"]["name"] == "osdu-perf-runner"
    assert values["serviceAccount"]["workloadIdentityClientId"] == "cid"


def test_build_values_serviceaccount_create_true_when_flag_set():
    runner = K8sRunner(_app_config())
    values = runner._build_values(
        inputs=_inputs(create_service_account=True),
        run_name="r",
        namespace="perf",
        image_ref="myacr.azurecr.io/osdu-perf:abc",
        create_service_account=True,
    )
    assert values["serviceAccount"]["create"] is True
    assert values["serviceAccount"]["workloadIdentityClientId"] == "cid"


def test_build_values_istio_ingress_renders_fields():
    runner = K8sRunner(
        _app_config(
            AksIngress(
                type="istio",
                host="perf.example.com",
                path_prefix="/locust",
                istio_gateway="istio-system/istio-gateway",
            )
        )
    )
    values = runner._build_values(
        inputs=_inputs(web_ui=True),
        run_name="r",
        namespace="perf",
        image_ref="myacr.azurecr.io/osdu-perf:abc",
    )
    assert values["ingress"]["type"] == "istio"
    assert values["ingress"]["host"] == "perf.example.com"
    assert values["ingress"]["istio"]["gateway"] == "istio-system/istio-gateway"


def test_chart_path_points_at_packaged_directory():
    path = _chart_path()
    assert (path / "Chart.yaml").is_file()
    assert (path / "values.yaml").is_file()
    assert (path / "templates" / "configmap.yaml").is_file()


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm not on PATH")
def test_helm_template_renders_full_release(tmp_path: Path):
    """If helm is installed, render the chart end-to-end and sanity-check output."""
    runner = K8sRunner(
        _app_config(
            AksIngress(type="istio", host="perf.example.com", path_prefix="/locust")
        )
    )
    values = runner._build_values(
        inputs=_inputs(web_ui=True),
        run_name="osdu-perf-test",
        namespace="perf",
        image_ref="myacr.azurecr.io/osdu-perf:abc",
    )
    values_file = tmp_path / "values.yaml"
    values_file.write_text(yaml.safe_dump(values), encoding="utf-8")

    proc = subprocess.run(
        [
            "helm",
            "template",
            "osdu-perf-test",
            str(_chart_path()),
            "--values",
            str(values_file),
            "--namespace",
            "perf",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "kind: ConfigMap" in out
    assert "kind: Service" in out
    assert "kind: Deployment" in out  # webui mode
    assert "kind: VirtualService" in out
    assert "osdu-perf.io/role: master" in out
    assert "osdu-perf.io/role: worker" in out
