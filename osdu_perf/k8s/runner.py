"""End-to-end orchestrator for ``osdu_perf run k8s``.

Builds + pushes the test image, renders a Helm values dict, then invokes
``helm upgrade --install`` against the bundled ``osdu-perf`` chart to roll
out Locust master + workers + (optional) Istio VirtualService or plain
Ingress for external web-UI access.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from ..config import AppConfig, PerformanceProfile
from ..errors import ConfigError
from ..telemetry import get_logger
from . import cluster
from .builder import ImageBuilder

_LOGGER = get_logger("k8s.runner")
_NAME_RE = re.compile(r"[^a-z0-9-]+")
_CHART_PKG = "osdu_perf.k8s.chart"


@dataclass(frozen=True)
class K8sRunInputs:
    """Inputs for one ``run k8s`` invocation."""

    host: str
    partition: str
    app_id: str
    test_directory: Path
    profile: PerformanceProfile
    labels: dict[str, str]
    scenario: str
    test_run_id_prefix: str = "perf"
    profile_name: str | None = None
    test_name: str | None = None
    image_tag: str | None = None
    skip_build: bool = False
    skip_push: bool = False
    skip_logs: bool = False
    web_ui: bool = False
    azure_config_relpath: str | None = None
    namespace_override: str | None = None
    create_service_account: bool = False


class K8sRunner:
    """Orchestrate a distributed Locust run on AKS via Helm."""

    def __init__(self, config: AppConfig) -> None:
        if not config.aks.is_configured:
            raise ConfigError(
                "aks.subscription_id, aks.resource_group, and aks.cluster_name are "
                "required for 'osdu_perf run k8s'. Add an 'aks:' block to azure_config.yaml."
            )
        if not config.aks.workload_identity_client_id:
            raise ConfigError(
                "aks.workload_identity_client_id is required so the pod's ServiceAccount "
                "can federate to AAD. Set it to the client_id of the user-assigned managed "
                "identity (or app registration) bound to the federated credential."
            )
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, inputs: K8sRunInputs) -> dict[str, Any]:
        run_name = _build_run_name(inputs)
        namespace = inputs.namespace_override or self._config.aks.namespace
        tag = inputs.image_tag or run_name

        # 1) Build + push image
        builder = ImageBuilder(self._config.container_registry)
        build_result = builder.build_and_push(
            inputs.test_directory,
            tag,
            skip_build=inputs.skip_build,
            skip_push=inputs.skip_push,
        )

        # 2) Fetch AKS credentials + ensure namespace
        cluster.require("az")
        cluster.require("kubectl")
        cluster.require("helm")
        self._fetch_credentials()
        self._ensure_namespace(namespace)

        # 2b) Preflight: confirm the ServiceAccount exists unless we
        # are about to create it via the chart. Fails fast with a
        # clear remediation hint instead of a 5-minute helm timeout.
        create_sa = (
            inputs.create_service_account
            or self._config.aks.create_service_account
        )
        if not create_sa:
            self._require_service_account(namespace)

        # 3) Helm install / upgrade
        values = self._build_values(
            inputs=inputs,
            run_name=run_name,
            namespace=namespace,
            image_ref=build_result.image_ref,
            create_service_account=create_sa,
        )
        self._helm_upgrade(run_name, namespace, values)

        # 4) Optionally stream master logs
        if not inputs.skip_logs and not inputs.web_ui:
            self._wait_and_stream(namespace, run_name)
        elif inputs.web_ui:
            self._wait_for_ready(namespace, run_name)

        portal_url = (
            "https://portal.azure.com/#@/resource/subscriptions/"
            f"{self._config.aks.subscription_id}/resourceGroups/"
            f"{self._config.aks.resource_group}/providers/"
            f"Microsoft.ContainerService/managedClusters/"
            f"{self._config.aks.cluster_name}/overview"
        )
        return {
            "runName": run_name,
            "namespace": namespace,
            "image": build_result.image_ref,
            "imagePushed": build_result.pushed,
            "scenario": inputs.scenario,
            "testName": inputs.test_name or inputs.scenario,
            "profileName": inputs.profile_name or "",
            "users": inputs.profile.users,
            "spawnRate": inputs.profile.spawn_rate,
            "runTime": inputs.profile.run_time,
            "engineInstances": inputs.profile.engine_instances,
            "host": inputs.host,
            "partition": inputs.partition,
            "appId": inputs.app_id,
            "labels": dict(inputs.labels),
            "aksCluster": self._config.aks.cluster_name,
            "resourceGroup": self._config.aks.resource_group,
            "subscriptionId": self._config.aks.subscription_id,
            "portalUrl": portal_url,
            "webUi": inputs.web_ui,
            "ingress": self._config.aks.ingress.type,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _fetch_credentials(self) -> None:
        aks = self._config.aks
        _LOGGER.info("Fetching AKS credentials for %s", aks.cluster_name)
        cluster.run(
            [
                "az",
                "aks",
                "get-credentials",
                "--subscription",
                str(aks.subscription_id),
                "--resource-group",
                str(aks.resource_group),
                "--name",
                str(aks.cluster_name),
                "--overwrite-existing",
                "--only-show-errors",
            ]
        )

    def _ensure_namespace(self, namespace: str) -> None:
        cluster.run(
            ["kubectl", "apply", "-f", "-"],
            stdin=(
                "apiVersion: v1\n"
                "kind: Namespace\n"
                "metadata:\n"
                f"  name: {namespace}\n"
            ),
        )

    def _require_service_account(self, namespace: str) -> None:
        """Verify that the configured ServiceAccount exists in *namespace*.

        Raises :class:`ConfigError` with a copy-pasteable remediation if
        it does not, instead of letting helm hang for 5 minutes on a
        ``serviceaccount \"...\" not found`` ReplicaSet event.
        """
        sa = self._config.aks.service_account
        client_id = self._config.aks.workload_identity_client_id or ""
        result = cluster.run(
            ["kubectl", "get", "serviceaccount", sa, "-n", namespace, "--ignore-not-found"],
            capture=True,
            check=False,
        )
        stdout = (result.stdout or "").strip()
        if result.returncode == 0 and stdout:
            return
        raise ConfigError(
            f"ServiceAccount '{namespace}/{sa}' not found on the cluster.\n"
            "  Either:\n"
            "    (a) re-run with '--create-service-account' (or set\n"
            "        aks.create_service_account: true in azure_config.yaml) so the\n"
            "        bundled Helm chart creates it with the Workload Identity\n"
            "        annotation, OR\n"
            "    (b) create it once manually:\n"
            "          kubectl apply -f - <<'EOF'\n"
            "          apiVersion: v1\n"
            "          kind: ServiceAccount\n"
            "          metadata:\n"
            f"            name: {sa}\n"
            f"            namespace: {namespace}\n"
            "            annotations:\n"
            f"              azure.workload.identity/client-id: {client_id}\n"
            "          EOF\n"
            "  Also confirm the UAMI has a federated credential bound to\n"
            f"  'system:serviceaccount:{namespace}:{sa}' and 'AcrPull' on the registry."
        )

    def _helm_upgrade(
        self, run_name: str, namespace: str, values: dict[str, Any]
    ) -> None:
        chart_path = _chart_path()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tmp:
            yaml.safe_dump(values, tmp, sort_keys=False)
            values_file = tmp.name
        _LOGGER.info("Helm upgrade --install %s (namespace=%s)", run_name, namespace)
        try:
            cluster.run(
                [
                    "helm",
                    "upgrade",
                    "--install",
                    run_name,
                    str(chart_path),
                    "--namespace",
                    namespace,
                    "--values",
                    values_file,
                    "--wait",
                    "--timeout",
                    "5m",
                ]
            )
        finally:
            try:
                Path(values_file).unlink()
            except OSError:
                pass

    def _wait_and_stream(self, namespace: str, run_name: str) -> None:
        master_label = f"osdu-perf.io/run-id={run_name},osdu-perf.io/role=master"
        cluster.run(
            [
                "kubectl",
                "wait",
                "--namespace",
                namespace,
                "--for=condition=Ready",
                "pod",
                "-l",
                master_label,
                "--timeout=300s",
            ],
            check=False,
        )
        _LOGGER.info("Streaming master logs (Ctrl+C to detach; the run keeps going)")
        cluster.stream(
            [
                "kubectl",
                "logs",
                "--namespace",
                namespace,
                "--follow",
                "--tail=200",
                "-l",
                master_label,
            ]
        )

    def _wait_for_ready(self, namespace: str, run_name: str) -> None:
        master_label = f"osdu-perf.io/run-id={run_name},osdu-perf.io/role=master"
        _LOGGER.info("Waiting for master pod to become Ready (web-UI mode)...")
        cluster.run(
            [
                "kubectl",
                "wait",
                "--namespace",
                namespace,
                "--for=condition=Ready",
                "pod",
                "-l",
                master_label,
                "--timeout=300s",
            ],
            check=False,
        )

    # ------------------------------------------------------------------
    # Helm values rendering
    # ------------------------------------------------------------------
    def _build_values(
        self,
        *,
        inputs: K8sRunInputs,
        run_name: str,
        namespace: str,
        image_ref: str,
        create_service_account: bool = False,
    ) -> dict[str, Any]:
        aks = self._config.aks
        repo, _, tag = image_ref.rpartition(":")
        if not repo:
            repo = image_ref
            tag = "latest"

        worker_count = max(0, inputs.profile.engine_instances - 1)
        extra_labels = (
            json.dumps(dict(inputs.labels), separators=(",", ":"))
            if inputs.labels
            else ""
        )
        ingress = aks.ingress
        return {
            "runName": run_name,
            "namespace": namespace,
            "image": {
                "repository": repo,
                "tag": tag,
                "pullPolicy": "Always",
            },
            "serviceAccount": {
                "name": aks.service_account,
                "create": bool(create_service_account),
                "workloadIdentityClientId": aks.workload_identity_client_id or "",
            },
            "mode": "webui" if inputs.web_ui else "headless",
            "master": {"replicas": 1},
            "workers": {"count": worker_count},
            "env": {
                "LOCUST_HOST": inputs.host,
                "LOCUST_USERS": str(inputs.profile.users),
                "LOCUST_SPAWN_RATE": str(inputs.profile.spawn_rate),
                "LOCUST_RUN_TIME": str(inputs.profile.run_time),
                "LOCUST_EXPECT_WORKERS": str(worker_count),
                "PARTITION": inputs.partition,
                "APPID": inputs.app_id,
                "AZURE_LOAD_TEST": "true",
                "OSDU_PERF_ENV": "AKS",
                "TEST_SCENARIO": inputs.scenario,
                "OSDU_PERF_PROFILE_NAME": inputs.profile_name or "",
                "OSDU_PERF_PROFILE_USERS": str(inputs.profile.users),
                "OSDU_PERF_PROFILE_SPAWN_RATE": str(inputs.profile.spawn_rate),
                "OSDU_PERF_PROFILE_RUN_TIME": str(inputs.profile.run_time),
                "OSDU_PERF_PROFILE_ENGINES": str(inputs.profile.engine_instances),
                "OSDU_PERF_TEST_NAME": inputs.test_name or "",
                "OSDU_PERF_TEST_RUN_ID_PREFIX": inputs.test_run_id_prefix or "",
                "OSDU_PERF_TEST_RUN_ID": run_name,
                "OSDU_PERF_AZURE_CONFIG": inputs.azure_config_relpath or "",
                "WEB_UI": "true" if inputs.web_ui else "false",
                "OSDU_PERF_EXTRA_LABELS": extra_labels,
            },
            "ingress": {
                "type": ingress.type,
                "host": ingress.host or "",
                "pathPrefix": ingress.path_prefix,
                "istio": {
                    "gateway": ingress.istio_gateway,
                    "timeout": ingress.istio_timeout,
                },
                "ingress": {
                    "className": ingress.ingress_class_name or "",
                    "annotations": dict(ingress.ingress_annotations),
                    "tls": [],
                },
            },
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _chart_path() -> Path:
    """Absolute path of the bundled Helm chart directory."""
    return Path(str(files(_CHART_PKG).joinpath("Chart.yaml").parent))


def _build_run_name(inputs: K8sRunInputs) -> str:
    """Compose a DNS-1123-safe run name (max 50 chars, lowercase a-z0-9-)."""
    parts = [
        inputs.scenario,
        inputs.test_run_id_prefix,
        datetime.now(timezone.utc).strftime("%y%m%d%H%M%S"),
    ]
    raw = "-".join(parts).lower()
    cleaned = _NAME_RE.sub("-", raw).strip("-")
    return cleaned[:50].rstrip("-") or "osdu-perf-run"


__all__ = ["K8sRunInputs", "K8sRunner"]
