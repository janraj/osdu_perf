"""Azure Load Test Resource Manager - handles Azure resource lifecycle operations."""

import logging
from typing import Dict, Any, Optional
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.loadtesting import LoadTestMgmtClient


class AzureLoadTestResourceManager:
    """Manages Azure Load Testing resources (create, delete, get operations)."""
    
    def __init__(
        self,
        subscription_id: str,
        resource_group_name: str,
        load_test_name: str,
        location: str,
        credential: Any,
        tags: Optional[Dict[str, str]] = None,
        logger: Optional[logging.Logger] = None,
        allow_resource_creation: bool = False,
    ):
        """Initialize the resource manager.

        Args:
            allow_resource_creation: When False (default), the manager will
                NEVER create a resource group or a load test resource. If the
                target resources don't already exist, an explicit error is
                raised so the user can fix the config or opt-in by setting
                ``azure_infra.allow_resource_creation: true`` in
                system_config.yaml.
        """
        self.subscription_id = subscription_id
        self.resource_group_name = resource_group_name
        self.load_test_name = load_test_name
        self.location = location
        self.credential = credential
        self.tags = tags or {"Environment": "Performance Testing", "Service": "OSDU"}
        self.logger = logger or logging.getLogger(__name__)
        self.allow_resource_creation = bool(allow_resource_creation)
        
        # Initialize SDK clients
        self._init_clients()
        
        self.logger.info(f"Resource Manager initialized for '{load_test_name}'")
    
    def _init_clients(self) -> None:
        """Initialize Azure SDK clients."""
        try:
            # Resource Management Client for resource group operations
            self.resource_client = ResourceManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
            
            # Load Test Management Client for resource operations
            self.loadtest_mgmt_client = LoadTestMgmtClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            self.logger.info(f"Azure SDK clients initialized successfully {self.subscription_id}")

        except Exception as e:
            self.logger.error(f"Failed to initialize Azure SDK clients: {e}")
            raise

    def create_resource_group(self) -> bool:
        """
        Create the resource group if it doesn't exist.
        
        Returns:
            bool: True if resource group exists or was created successfully
        """
        try:
            self.logger.info(f"Checking if resource group '{self.resource_group_name}' exists...")
            
            # Check if resource group exists
            try:
                rg = self.resource_client.resource_groups.get(self.resource_group_name)
                self.logger.info(f"Resource group '{self.resource_group_name}' already exists {rg}")
                return True
            except Exception as e:
                # Resource group doesn't exist.
                if not self.allow_resource_creation:
                    msg = (
                        f"Resource group '{self.resource_group_name}' does not exist in "
                        f"subscription '{self.subscription_id}' and automatic resource "
                        f"creation is disabled. Either create it manually, verify the "
                        f"resource_group / subscription_id in system_config.yaml are "
                        f"correct, or opt in by setting "
                        f"`azure_infra.allow_resource_creation: true` in "
                        f"system_config.yaml."
                    )
                    self.logger.error(f"❌ {msg}")
                    raise RuntimeError(msg) from e

                # Opt-in path: create it
                self.logger.info(f"Creating resource group '{self.resource_group_name}'... (error checking existence: {e})")

                rg_params = {
                    'location': self.location,
                    'tags': {
                        'Environment': 'Performance Testing',
                        'Service': 'OSDU',
                        'CreatedBy': 'AzureLoadTestSDKManager'
                    }
                }
                
                result = self.resource_client.resource_groups.create_or_update(
                    self.resource_group_name,
                    rg_params
                )
                
                self.logger.info(f"Resource group '{self.resource_group_name}' created successfully, {result.id}")
                return True
                
        except Exception as e:
            error_msg = (
                f"Failed to create resource group '{self.resource_group_name}' in location '{self.location}'. "
                f"Error: {str(e)}"
            )
            self.logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg) from e
    
    def create_load_test_resource(self) -> Optional[Dict[str, Any]]:
        """
        Create the Azure Load Test resource.
        
        Returns:
            Dict[str, Any]: The created load test resource data, or None if failed
        """
        load_test_data = {
                "location": self.location,
                "identity": {"type": "SystemAssigned"},
                "tags": self.tags,
                "properties": {}
        }
        
        # Ensure resource group exists
        self.logger.info(f"Check resource group '{self.resource_group_name}' exists, if not create one")
        self.create_resource_group()
         
        try:
            self.logger.info(f"Checking if load test resource '{self.load_test_name}' exists...")
            resource = self.loadtest_mgmt_client.load_tests.get(
                resource_group_name=self.resource_group_name,
                load_test_name=self.load_test_name
            )
            self.logger.info(f"Load test resource '{self.load_test_name}' already exists, {resource.data_plane_uri}, resource.identity.principal_id={resource.identity.principal_id}")

        except Exception as e:
            # Resource doesn't exist.
            if not self.allow_resource_creation:
                msg = (
                    f"Azure Load Test resource '{self.load_test_name}' does not "
                    f"exist in resource group '{self.resource_group_name}' "
                    f"(subscription '{self.subscription_id}') and automatic "
                    f"resource creation is disabled. Either create it manually, "
                    f"double-check --loadtest-name / system_config.yaml, or opt "
                    f"in by setting `azure_infra.allow_resource_creation: "
                    f"true` in system_config.yaml."
                )
                self.logger.error(f"❌ {msg}")
                raise RuntimeError(msg) from e

            # Opt-in path: create it
            self.logger.info(f"Creating new load test resource... {self.load_test_name}")

            try:
                create_operation = self.loadtest_mgmt_client.load_tests.begin_create_or_update(
                    resource_group_name=self.resource_group_name,
                    load_test_name=self.load_test_name,
                    load_test_resource=load_test_data
                )
                
                # Wait for creation to complete
                self.logger.info(f"Waiting for load test resource '{self.load_test_name}' creation to complete...")
                resource = create_operation.result()
                self.logger.info(f"Load test resource '{self.load_test_name}' created successfully")
                self.logger.info(f"  Resource ID: {resource.id}")
                self.logger.info(f"  Data Plane URI: {resource.data_plane_uri} identity.principal_id={resource.identity.principal_id}")
            except Exception as e:
                error_msg = (
                    f"Failed to create Azure Load Testing resource '{self.load_test_name}' "
                    f"in resource group '{self.resource_group_name}'. "
                    f"Error: {str(e)}"
                )
                self.logger.error(f"❌ {error_msg}")
                raise RuntimeError(error_msg) from e

        return resource.as_dict()
    
    def get_load_test_resource(self) -> Optional[Dict[str, Any]]:
        """
        Get details of existing load testing resource.
        
        Returns:
            Dict[str, Any]: Resource details or None if not found
        """
        try:
            resource = self.loadtest_mgmt_client.load_tests.get(
                resource_group_name=self.resource_group_name,
                load_test_name=self.load_test_name
            )
            return resource.as_dict()
            
        except Exception as e:
            self.logger.warning(f"Load Testing resource '{self.load_test_name}' not found: {e}")
            return None