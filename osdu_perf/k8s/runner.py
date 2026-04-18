"""End-to-end orchestrator for ``osdu_perf run k8s``.

Mirrors :class:`osdu_perf.azure.runner.AzureRunner` but targets an AKS
cluster: build + push image, fetch cluster credentials, render manifests,
``kubectl apply``, then stream master logs until the Job completes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import AppConfig, PerformanceProfile
from ..errors import ConfigError
from ..telemetry import get_logger
from . import cluster
from .builder import ImageBuilder
from .manifests import render_all

_LOGGER = get_logger("k8s.runner")
_NAME_RE = re.compile(r"[^a-z0-9-]+")


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


class K8sRunner:
    """Orchestrate a distributed Locust run on AKS."""

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

        # 2) Fetch AKS credentials (idempotent — always merges into ~/.kube/config)
        self._fetch_credentials()

        # 3) Render + apply manifests
        manifest = render_all(
            self._template_values(
                inputs=inputs,
                run_name=run_name,
                namespace=namespace,
                image_ref=build_result.image_ref,
            ),
            worker_count=max(0, inputs.profile.engine_instances - 1),
        )
        _LOGGER.info(
            "Applying %d manifest doc(s) to namespace %s", manifest.count("\n---"), namespace
        )
        cluster.run(["kubectl", "apply", "-f", "-"], stdin=manifest)

        # 4) Optionally stream master logs until completion
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
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _fetch_credentials(self) -> None:
        cluster.require("az")
        cluster.require("kubectl")
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

    def _wait_and_stream(self, namespace: str, run_name: str) -> None:
        # Wait briefly for the master pod to schedule, then stream until
        # the Job completes. Workers are best-effort tailed via labels.
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

    def _template_values(
        self,
        *,
        inputs: K8sRunInputs,
        run_name: str,
        namespace: str,
        image_ref: str,
    ) -> dict[str, str]:
        aks = self._config.aks
        return {
            "RUN_NAME": run_name,
            "NAMESPACE": namespace,
            "SERVICE_ACCOUNT": aks.service_account,
            "WORKLOAD_IDENTITY_CLIENT_ID": aks.workload_identity_client_id or "",
            "IMAGE": image_ref,
            "LOCUST_HOST": inputs.host,
            "LOCUST_USERS": str(inputs.profile.users),
            "LOCUST_SPAWN_RATE": str(inputs.profile.spawn_rate),
            "LOCUST_RUN_TIME": str(inputs.profile.run_time),
            "LOCUST_EXPECT_WORKERS": str(max(0, inputs.profile.engine_instances - 1)),
            "ENGINE_INSTANCES": str(inputs.profile.engine_instances),
            "WEB_UI": "true" if inputs.web_ui else "false",
            "AZURE_CONFIG_PATH": inputs.azure_config_relpath or "",
            "PARTITION": inputs.partition,
            "APPID": inputs.app_id,
            "SCENARIO": inputs.scenario,
            "PROFILE_NAME": inputs.profile_name or "",
            "TEST_NAME": inputs.test_name or "",
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _build_run_name(inputs: K8sRunInputs) -> str:
    """Compose a DNS-1123-safe run name (max 63 chars, lowercase a-z0-9-).

    The prefix already embeds the test name (see
    :func:`osdu_perf.cli.commands._run_common.resolved_test_run_id_prefix`),
    so we do not repeat it here.
    """
    parts = [
        inputs.scenario,
        inputs.test_run_id_prefix,
        datetime.now(timezone.utc).strftime("%y%m%d%H%M%S"),
    ]
    raw = "-".join(parts).lower()
    cleaned = _NAME_RE.sub("-", raw).strip("-")
    return cleaned[:50].rstrip("-") or "osdu-perf-run"


__all__ = ["K8sRunInputs", "K8sRunner"]
