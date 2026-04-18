"""High-level Azure Load Test orchestrator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from azure.developer.loadtesting import LoadTestAdministrationClient, LoadTestRunClient
from azure.identity import AzureCliCredential

from ..config import AppConfig, PerformanceProfile
from ..errors import AzureResourceError, ConfigError
from ..telemetry import get_logger
from .entitlements import EntitlementProvisioner
from .executor import TestExecutor
from .files import TestFileUploader
from .resources import AzureResourceProvisioner

_LOGGER = get_logger("azure.runner")
_SECONDS_MULTIPLIERS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True)
class AzureRunInputs:
    """Inputs for a single ALT run — resolved from :class:`AppConfig` + CLI."""

    host: str
    partition: str
    app_id: str
    osdu_token: str
    test_directory: Path
    profile: PerformanceProfile
    labels: dict[str, str]
    scenario: str
    test_run_id_prefix: str = "perf"
    profile_name: str | None = None
    test_name: str | None = None
    """Stable ALT test-name component. Defaults to ``scenario`` when unset.

    The ALT *test id* (the load test definition that groups runs) is
    ``<scenario>_<test_name>`` — this stays stable across invocations so
    every run nests under the same test. Each invocation still gets a
    unique *run id*: ``<scenario>_<test_name>_<prefix>_<UTC_ts>``.
    """


class AzureRunner:
    """Orchestrate an end-to-end Azure Load Test run.

    The runner:

    1. Ensures the resource group + ALT resource exist.
    2. Creates the test definition and uploads local test files.
    3. Provisions OSDU entitlements for the ALT managed identity.
    4. Starts the test run.
    """

    _API_VERSION = "2024-12-01-preview"

    def __init__(self, config: AppConfig) -> None:
        alt = config.azure_load_test
        if not alt.subscription_id:
            raise ConfigError("azure_load_test.subscription_id is required")
        if not alt.resource_group:
            raise ConfigError("azure_load_test.resource_group is required")
        if not alt.name:
            raise ConfigError("azure_load_test.name is required")

        self._config = config
        self._credential = AzureCliCredential()
        self._provisioner = AzureResourceProvisioner(
            subscription_id=alt.subscription_id,
            resource_group=alt.resource_group,
            load_test_name=alt.name,
            location=alt.location,
            credential=self._credential,
            allow_resource_creation=alt.allow_resource_creation,
        )
        self._admin_client: LoadTestAdministrationClient | None = None
        self._run_client: LoadTestRunClient | None = None
        self._principal_id: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, inputs: AzureRunInputs) -> dict[str, Any]:
        resource = self._provisioner.ensure_load_test_resource()
        self._bind_data_plane(resource)

        test_name = _build_test_name(inputs)
        run_id = _build_test_run_id(inputs, test_name)
        self._create_test(test_name, inputs)
        self._upload_files(test_name, inputs.test_directory)
        self._provision_entitlements(inputs)
        result = TestExecutor(self._run_client).start(  # type: ignore[arg-type]
            test_name, display_name=run_id
        )
        alt = self._config.azure_load_test
        portal_url = (
            "https://portal.azure.com/#blade/Microsoft_Azure_CloudNativeTesting/"
            "TestRunReport.ReactView//resourceId/"
            f"%2fsubscriptions%2f{alt.subscription_id}"
            f"%2fresourcegroups%2f{alt.resource_group}"
            "%2fproviders%2fmicrosoft.loadtestservice%2floadtests%2f"
            f"{alt.name}"
            f"/testId/{test_name}"
            f"/testRunId/{result.get('testRunId')}"
        )
        return {
            **result,
            "testId": test_name,
            "scenario": inputs.scenario,
            "testName": inputs.test_name or inputs.scenario,
            "profileName": inputs.profile_name or self._resolve_profile_name(inputs.profile),
            "users": inputs.profile.users,
            "spawnRate": inputs.profile.spawn_rate,
            "runTime": inputs.profile.run_time,
            "engineInstances": inputs.profile.engine_instances,
            "host": inputs.host,
            "partition": inputs.partition,
            "appId": inputs.app_id,
            "labels": dict(inputs.labels),
            "loadTestResource": alt.name,
            "resourceGroup": alt.resource_group,
            "subscriptionId": alt.subscription_id,
            "portalUrl": portal_url,
        }

    def _resolve_profile_name(self, profile: PerformanceProfile) -> str | None:
        for name, candidate in self._config.profiles.items():
            if candidate is profile or candidate == profile:
                return name
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _bind_data_plane(self, resource: dict[str, Any]) -> None:
        data_plane_uri = resource.get("data_plane_uri")
        principal_id = (resource.get("identity") or {}).get("principal_id")
        if not data_plane_uri or not principal_id:
            raise AzureResourceError("Load test resource is missing data_plane_uri or principal_id")
        # The azure-developer-loadtesting SDK formats its base URL as
        # ``https://{Endpoint}``, so pass just the hostname (strip any
        # scheme we might have received).
        endpoint = data_plane_uri
        for prefix in ("https://", "http://"):
            if endpoint.startswith(prefix):
                endpoint = endpoint[len(prefix) :]
                break
        endpoint = endpoint.rstrip("/")
        self._principal_id = principal_id
        self._admin_client = LoadTestAdministrationClient(endpoint, self._credential)
        self._run_client = LoadTestRunClient(endpoint, self._credential)

    def _create_test(self, test_name: str, inputs: AzureRunInputs) -> None:
        assert self._admin_client is not None
        _LOGGER.info("Creating ALT test definition '%s'", test_name)
        env_vars = {
            "LOCUST_HOST": inputs.host,
            "PARTITION": inputs.partition,
            "APPID": inputs.app_id,
            "LOCUST_USERS": str(inputs.profile.users),
            "LOCUST_SPAWN_RATE": str(inputs.profile.spawn_rate),
            "LOCUST_RUN_TIME": str(_to_seconds(inputs.profile.run_time)),
            "AZURE_LOAD_TEST": "true",
            "OSDU_PERF_ENV": "Azure Load Test",
            "TEST_SCENARIO": inputs.scenario,
            "ADME_BEARER_TOKEN": inputs.osdu_token,
            "OSDU_PERF_PROFILE_NAME": inputs.profile_name
            or self._resolve_profile_name(inputs.profile)
            or "",
            "OSDU_PERF_PROFILE_USERS": str(inputs.profile.users),
            "OSDU_PERF_PROFILE_SPAWN_RATE": str(inputs.profile.spawn_rate),
            "OSDU_PERF_PROFILE_RUN_TIME": str(inputs.profile.run_time),
            "OSDU_PERF_PROFILE_ENGINES": str(inputs.profile.engine_instances),
            "OSDU_PERF_TEST_NAME": inputs.test_name or "",
        }
        body = {
            "displayName": test_name[:50],
            "description": f"OSDU perf run: {inputs.scenario}",
            "kind": "Locust",
            "engineBuiltinIdentityType": "SystemAssigned",
            "loadTestConfiguration": {
                "engineInstances": inputs.profile.engine_instances,
                "splitAllCSVs": False,
                "quickStartTest": False,
            },
            "passFailCriteria": {"passFailMetrics": {}},
            "environmentVariables": env_vars,
            "secrets": {},
        }
        self._admin_client.create_or_update_test(test_id=test_name, body=body)

    def _upload_files(self, test_name: str, directory: Path) -> None:
        assert self._admin_client is not None
        uploader = TestFileUploader(self._admin_client)
        files = uploader.discover(directory)
        if not files:
            raise AzureResourceError(
                f"No test files found in '{directory}'. Expected locustfile.py, "
                f"perf_*_test.py, requirements.txt, etc."
            )
        uploader.upload(test_name, files)

    def _provision_entitlements(self, inputs: AzureRunInputs) -> None:
        assert self._principal_id is not None
        provisioner = EntitlementProvisioner(self._credential, self._principal_id)
        result = provisioner.provision(
            host=inputs.host,
            partition=inputs.partition,
            osdu_token=inputs.osdu_token,
        )
        if not result.success:
            raise AzureResourceError(f"Entitlement provisioning failed: {result.message}")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _build_test_name(inputs: AzureRunInputs) -> str:
    """ALT test id — stable across runs so every invocation reuses it.

    Formed as ``<scenario>_<test_name>`` (``test_name`` defaults to the
    scenario when not supplied, giving ``<scenario>_<scenario>``; set
    ``run_scenario.test_name`` or ``--test-name`` to customise).
    """
    component = (inputs.test_name or inputs.scenario).strip()
    return _slug(f"{inputs.scenario}_{component}")


def _build_test_run_id(inputs: AzureRunInputs, test_name: str) -> str:
    """Unique ALT test-run id, nested under ``test_name``.

    Formed as ``<test_name>_<prefix>_<UTC_ts>``.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    prefix = (inputs.test_run_id_prefix or "perf").strip() or "perf"
    return _slug(f"{test_name}_{prefix}_{timestamp}")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned.lower() or "osdu_perf_test"


def _to_seconds(run_time: str) -> int:
    value = run_time.strip().lower()
    if not value:
        return 0
    if value.isdigit():
        return int(value)
    match = re.fullmatch(r"(\d+)([smhd])", value)
    if not match:
        raise ConfigError(f"Invalid run_time '{run_time}' (expected e.g. '60s', '5m', '1h')")
    amount, unit = match.groups()
    return int(amount) * _SECONDS_MULTIPLIERS[unit]


__all__ = ["AzureRunner", "AzureRunInputs"]
