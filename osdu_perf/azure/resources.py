"""Resource-group and Azure Load Test resource lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from azure.mgmt.loadtesting import LoadTestMgmtClient
from azure.mgmt.resource import ResourceManagementClient

from ..errors import AzureResourceError
from ..telemetry import get_logger

_LOGGER = get_logger("azure.resources")

_DEFAULT_TAGS: dict[str, str] = {
    "Environment": "Performance Testing",
    "Service": "OSDU",
}


class AzureResourceProvisioner:
    """Ensures the resource group and Azure Load Test resource exist.

    When ``allow_resource_creation`` is False (the default) and a resource
    does not exist, an :class:`AzureResourceError` is raised with a clear
    migration hint.
    """

    def __init__(
        self,
        *,
        subscription_id: str,
        resource_group: str,
        load_test_name: str,
        location: str,
        credential: Any,
        tags: Mapping[str, str] | None = None,
        allow_resource_creation: bool = False,
    ) -> None:
        self._subscription_id = subscription_id
        self._resource_group = resource_group
        self._load_test_name = load_test_name
        self._location = location
        self._credential = credential
        self._tags = dict(tags or _DEFAULT_TAGS)
        self._allow_creation = allow_resource_creation
        self._resource_client = ResourceManagementClient(credential, subscription_id)
        self._loadtest_client = LoadTestMgmtClient(credential, subscription_id)

    # ------------------------------------------------------------------
    # Resource group
    # ------------------------------------------------------------------
    def ensure_resource_group(self) -> None:
        """Create the resource group if allowed, else verify it exists."""
        try:
            self._resource_client.resource_groups.get(self._resource_group)
            _LOGGER.info("Resource group '%s' exists", self._resource_group)
            return
        except Exception as exc:
            if not self._allow_creation:
                raise AzureResourceError(
                    f"Resource group '{self._resource_group}' does not exist in "
                    f"subscription '{self._subscription_id}'. Either create it "
                    f"manually or set 'azure_load_test.allow_resource_creation: true' "
                    f"in system_config.yaml."
                ) from exc

        _LOGGER.info("Creating resource group '%s'", self._resource_group)
        self._resource_client.resource_groups.create_or_update(
            self._resource_group,
            {"location": self._location, "tags": self._tags},
        )

    # ------------------------------------------------------------------
    # Load test resource
    # ------------------------------------------------------------------
    def ensure_load_test_resource(self) -> dict[str, Any]:
        """Ensure the Azure Load Test resource exists; return its dict form."""
        self.ensure_resource_group()
        try:
            existing = self._loadtest_client.load_tests.get(
                resource_group_name=self._resource_group,
                load_test_name=self._load_test_name,
            )
            _LOGGER.info(
                "Load test '%s' exists (dataPlaneUri=%s)",
                self._load_test_name,
                getattr(existing, "data_plane_uri", None),
            )
            return existing.as_dict()
        except Exception as exc:
            if not self._allow_creation:
                raise AzureResourceError(
                    f"Azure Load Test resource '{self._load_test_name}' does not "
                    f"exist in resource group '{self._resource_group}'. Either "
                    f"create it manually, check --load-test-name, or set "
                    f"'azure_load_test.allow_resource_creation: true' in "
                    f"system_config.yaml."
                ) from exc

        _LOGGER.info("Creating load test resource '%s'", self._load_test_name)
        poller = self._loadtest_client.load_tests.begin_create_or_update(
            resource_group_name=self._resource_group,
            load_test_name=self._load_test_name,
            load_test_resource={
                "location": self._location,
                "identity": {"type": "SystemAssigned"},
                "tags": self._tags,
                "properties": {},
            },
        )
        created = poller.result()
        _LOGGER.info("Load test resource ready (id=%s)", created.id)
        return created.as_dict()


__all__ = ["AzureResourceProvisioner"]
