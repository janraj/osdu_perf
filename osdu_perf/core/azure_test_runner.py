"""
Azure Load Test Manager

A class-based implementation following SOLID principles for managing Azure Load Testing resources.
Uses Azure CLI authentication for simplicity and security.

Author: OSDU Performance Testing Team
Date: September 2025
"""

import logging
import json
import requests
from typing import Dict, Any, Optional, List
from azure.identity import AzureCliCredential


class AzureLoadTestRunner:
    """
    Azure Load Test Manager using REST API calls instead of SDK.
    
    Single Responsibility: Manages Azure Load Testing resources via REST
    Open/Closed: Extensible for additional load testing operations
    Liskov Substitution: Can be extended with specialized managers
    Interface Segregation: Clear, focused public interface
    Dependency Inversion: Depends on Azure REST API abstractions
    """
    
    def __init__(self, 
                 subscription_id: str,
                 resource_group_name: str,
                 load_test_name: str,
                 location: str = "eastus",
                 tags: Optional[Dict[str, str]] = None):
        """
        Initialize the Azure Load Test Manager.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group_name: Resource group name
            load_test_name: Name for the load test resource
            location: Azure region (default: "eastus")
            tags: Dictionary of tags to apply to resources
        """
        # Store configuration
        self.subscription_id = subscription_id
        self.resource_group_name = resource_group_name
        self.load_test_name = load_test_name
        self.location = location
        self.tags = tags or {"Environment": "Performance Testing", "Service": "OSDU"}
        
        # Azure API endpoints
        self.management_base_url = "https://management.azure.com"
        self.api_version = "2024-12-01-preview"
        
        # Initialize logger
        self._setup_logging()
        
        # Initialize Azure credential
        self._credential = self._initialize_credential()
        
        # Log initialization
        self.logger.info(f"Azure Load Test Manager initialized (REST API)")
        self.logger.info(f"Subscription: {self.subscription_id}")
        self.logger.info(f"Resource Group: {self.resource_group_name}")
        self.logger.info(f"Load Test Name: {self.load_test_name}")
        self.logger.info(f"Location: {self.location}")
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _initialize_credential(self) -> AzureCliCredential:
        """Initialize Azure CLI credential."""
        try:
            credential = AzureCliCredential()
            self.logger.info("✅ Azure CLI credential initialized successfully")
            return credential
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Azure CLI credential: {e}")
            raise
    
    def _get_access_token(self) -> str:
        """Get Azure management API access token."""
        try:
            token = self._credential.get_token("https://management.azure.com/.default")
            return token.token
        except Exception as e:
            self.logger.error(f"❌ Failed to get access token: {e}")
            raise
    
    def _make_request(self, method: str, url: str, data: Optional[Dict] = None) -> requests.Response:
        """Make authenticated request to Azure REST API."""
        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"❌ Request failed: {e}")
            raise
    
    def ensure_resource_group_exists(self) -> bool:
        """
        Ensure the resource group exists, create if it doesn't.
        
        Returns:
            bool: True if resource group exists or was created successfully
        """
        try:
            self.logger.info(f"🔍 Checking if resource group '{self.resource_group_name}' exists...")
            
            # Check if resource group exists
            url = (f"{self.management_base_url}/subscriptions/{self.subscription_id}"
                  f"/resourceGroups/{self.resource_group_name}?api-version=2021-04-01")
            
            response = self._make_request("GET", url)
            
            if response.status_code == 200:
                self.logger.info(f"✅ Resource group '{self.resource_group_name}' already exists")
                return True
            elif response.status_code == 404:
                self.logger.info(f"📁 Creating resource group '{self.resource_group_name}'...")
                
                # Create the resource group
                rg_data = {
                    "location": self.location,
                    "tags": self.tags
                }
                
                create_response = self._make_request("PUT", url, rg_data)
                
                if create_response.status_code in [200, 201]:
                    self.logger.info(f"✅ Resource group '{self.resource_group_name}' created successfully")
                    return True
                else:
                    self.logger.error(f"❌ Failed to create resource group. Status: {create_response.status_code}, Response: {create_response.text}")
                    create_response.raise_for_status()
            else:
                self.logger.error(f"❌ Unexpected response checking resource group. Status: {response.status_code}, Response: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            self.logger.error(f"❌ Error ensuring resource group exists: {e}")
            raise
    
    def check_load_test_exists(self) -> bool:
        """
        Check if the load test resource already exists using REST API.
        
        Returns:
            bool: True if load test exists, False otherwise
        """
        try:
            self.logger.info(f"🔍 (REST) Checking if load test '{self.load_test_name}' exists...")
            
            url = (f"{self.management_base_url}/subscriptions/{self.subscription_id}"
                  f"/resourceGroups/{self.resource_group_name}"
                  f"/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}"
                  f"?api-version={self.api_version}")
            
            response = self._make_request("GET", url)
            
            if response.status_code == 200:
                self.logger.info(f"✅ (REST) Load test '{self.load_test_name}' exists")
                return True
            elif response.status_code == 404:
                self.logger.info(f"ℹ️ (REST) Load test '{self.load_test_name}' does not exist")
                return False
            else:
                self.logger.error(f"❌ (REST) Unexpected status {response.status_code} checking load test: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            self.logger.error(f"❌ (REST) Error checking load test existence: {e}")
            raise
    
    def create_load_test(self) -> Optional[Dict[str, Any]]:
        """
        Create the Azure Load Test resource using REST API.
        
        Returns:
            Dict[str, Any]: The created load test resource data, or None if failed
        """
        try:
            # Define load test resource properties
            load_test_data = {
                "location": self.location,
                "identity": {"type": "SystemAssigned"},
                "tags": self.tags,
                "properties": {}
            }

            self.logger.info(f"� (REST) Creating load test resource '{self.load_test_name}'...")
            
            url = (f"{self.management_base_url}/subscriptions/{self.subscription_id}"
                  f"/resourceGroups/{self.resource_group_name}"
                  f"/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}"
                  f"?api-version={self.api_version}")
            
            response = self._make_request("PUT", url, load_test_data)
            
            if response.status_code in [200, 201, 202]:
                result = response.json() if response.content else {}
                self.logger.info(f"✅ (REST) Load test '{self.load_test_name}' created successfully")
                
                # Log key information
                if result:
                    self.logger.info(f"   Resource ID: {result.get('id', 'N/A')}")
                    properties = result.get('properties', {})
                    if 'dataPlaneURI' in properties:
                        self.logger.info(f"   Data Plane URI: {properties['dataPlaneURI']}")
                
                return result
            else:
                self.logger.error(f"❌ (REST) Failed to create load test. Status: {response.status_code}, Response: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            self.logger.error(f"❌ (REST) Error creating load test: {e}")
            raise
    
    def get_load_test(self) -> Optional[Dict[str, Any]]:
        """
        Get the existing load test resource using REST API.
        
        Returns:
            Dict[str, Any]: The load test resource data, or None if not found
        """
        try:
            url = (f"{self.management_base_url}/subscriptions/{self.subscription_id}"
                  f"/resourceGroups/{self.resource_group_name}"
                  f"/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}"
                  f"?api-version={self.api_version}")
            
            response = self._make_request("GET", url)
            
            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"✅ (REST) Retrieved load test '{self.load_test_name}'")
                return result
            elif response.status_code == 404:
                self.logger.warning(f"⚠️ (REST) Load test '{self.load_test_name}' not found")
                return None
            else:
                self.logger.error(f"❌ (REST) Error retrieving load test. Status: {response.status_code}, Response: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            self.logger.error(f"❌ (REST) Error retrieving load test: {e}")
            raise
    
    def list_load_tests(self) -> List[Dict[str, Any]]:
        """
        List all load test resources in the resource group using REST API.
        
        Returns:
            List[Dict[str, Any]]: List of load test resources
        """
        try:
            self.logger.info(f"📋 (REST) Listing load tests in resource group '{self.resource_group_name}'...")
            
            url = (f"{self.management_base_url}/subscriptions/{self.subscription_id}"
                  f"/resourceGroups/{self.resource_group_name}"
                  f"/providers/Microsoft.LoadTestService/loadtests"
                  f"?api-version={self.api_version}")
            
            response = self._make_request("GET", url)
            
            if response.status_code == 200:
                result = response.json()
                load_tests = result.get('value', [])
                
                self.logger.info(f"✅ (REST) Found {len(load_tests)} load test(s)")
                for lt in load_tests:
                    name = lt.get('name', 'Unknown')
                    location = lt.get('location', 'Unknown')
                    self.logger.info(f"   - {name} (Location: {location})")
                
                return load_tests
            else:
                self.logger.error(f"❌ (REST) Error listing load tests. Status: {response.status_code}, Response: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            self.logger.error(f"❌ (REST) Error listing load tests: {e}")
            raise
    
    def get_load_test_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the load test resource using REST API.
        
        Returns:
            Dict[str, Any]: Load test information
        """
        try:
            load_test = self.get_load_test()
            if not load_test:
                return {"exists": False}
            
            properties = load_test.get('properties', {})
            identity = load_test.get('identity', {})
            
            info = {
                "exists": True,
                "name": load_test.get('name'),
                "id": load_test.get('id'),
                "location": load_test.get('location'),
                "data_plane_uri": properties.get('dataPlaneURI'),
                "provisioning_state": properties.get('provisioningState'),
                "tags": load_test.get('tags', {}),
                "identity": {
                    "type": identity.get('type'),
                    "principal_id": identity.get('principalId')
                }
            }
            
            return info
            
        except Exception as e:
            self.logger.error(f"❌ (REST) Error getting load test info: {e}")
            raise


def main():
    """
    Example usage of the AzureLoadTestManager class.
    """
    # Configuration
    SUBSCRIPTION_ID = "015ab1e4-bd82-4c0d-ada9-0f9e9c68e0c4"
    RESOURCE_GROUP = "janrajcj-rg"
    LOAD_TEST_NAME = "janraj-loadtest-instance"
    LOCATION = "eastus"
    
    try:
        print("🚀 Azure Load Test Manager - SOLID Principles Implementation")
        print("=" * 60)

        # Initialize the runner
        runner = AzureLoadTestRunner(
            subscription_id=SUBSCRIPTION_ID,
            resource_group_name=RESOURCE_GROUP,
            load_test_name=LOAD_TEST_NAME,
            location=LOCATION,
            tags={"Environment": "Demo", "Project": "OSDU"}
        )
        
        # Create the load test
        load_test = runner.create_load_test()
        
        if load_test:
            print(f"✅ Load Testing instance created: {load_test['id']}")
            
            # Get detailed info
            info = runner.get_load_test_info()
            print(f"📊 Load Test Details:")
            print(f"   Name: {info.get('name')}")
            print(f"   Location: {info.get('location')}")
            print(f"   Data Plane URI: {info.get('data_plane_uri')}")
            print(f"   Provisioning State: {info.get('provisioning_state')}")
        
        print("=" * 60)
        print("✅ Azure Load Test Manager execution completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔍 Troubleshooting:")
        print("1. Ensure Azure CLI is installed: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")
        print("2. Login to Azure CLI: az login")
        print("3. Verify subscription: az account show")
        print("4. Check permissions for creating resources")


if __name__ == "__main__":
    main()