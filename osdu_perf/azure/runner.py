"""High-level Azure Load Test orchestrator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from azure.developer.loadtesting import LoadTestAdministrationClient, LoadTestRunClient
from azure.identity import AzureCliCredential

from ..config import AppConfig, TestDefaults
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
    settings: TestDefaults
    tags: dict[str, str]
    scenario: str


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
        infra = config.azure_infra
        if not infra.subscription_id:
            raise ConfigError("azure_infra.subscription_id is required")
        if not infra.resource_group:
            raise ConfigError("azure_infra.resource_group is required")
        if not infra.azure_load_test.name:
            raise ConfigError("azure_infra.azure_load_test.name is required")

        self._config = config
        self._credential = AzureCliCredential()
        self._provisioner = AzureResourceProvisioner(
            subscription_id=infra.subscription_id,
            resource_group=infra.resource_group,
            load_test_name=infra.azure_load_test.name,
            location=infra.location,
            credential=self._credential,
            allow_resource_creation=infra.allow_resource_creation,
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
        self._create_test(test_name, inputs)
        self._upload_files(test_name, inputs.test_directory)
        self._provision_entitlements(inputs)
        return TestExecutor(self._run_client).start(test_name)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _bind_data_plane(self, resource: dict[str, Any]) -> None:
        data_plane_uri = resource.get("data_plane_uri")
        principal_id = (resource.get("identity") or {}).get("principal_id")
        if not data_plane_uri or not principal_id:
            raise AzureResourceError(
                "Load test resource is missing data_plane_uri or principal_id"
            )
        endpoint = (
            data_plane_uri if data_plane_uri.startswith("https://")
            else f"https://{data_plane_uri}"
        )
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
            "LOCUST_USERS": str(inputs.settings.users),
            "LOCUST_SPAWN_RATE": str(inputs.settings.spawn_rate),
            "LOCUST_RUN_TIME": str(_to_seconds(inputs.settings.run_time)),
            "AZURE_LOAD_TEST": "true",
            "TEST_SCENARIO": inputs.scenario,
            "ADME_BEARER_TOKEN": inputs.osdu_token,
        }
        body = {
            "displayName": test_name[:50],
            "description": inputs.settings.test_run_id_description,
            "kind": "Locust",
            "engineBuiltinIdentityType": "SystemAssigned",
            "loadTestConfiguration": {
                "engineInstances": inputs.settings.engine_instances,
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
            raise AzureResourceError(
                f"Entitlement provisioning failed: {result.message}"
            )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _build_test_name(inputs: AzureRunInputs) -> str:
    prefix = inputs.settings.test_name_prefix
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    raw = f"{prefix}_{inputs.scenario}_{timestamp}"
    return _slug(raw)


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
        raise ConfigError(
            f"Invalid run_time '{run_time}' (expected e.g. '60s', '5m', '1h')"
        )
    amount, unit = match.groups()
    return int(amount) * _SECONDS_MULTIPLIERS[unit]


__all__ = ["AzureRunner", "AzureRunInputs"]
