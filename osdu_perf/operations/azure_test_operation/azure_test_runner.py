"""
Azure Load Test Manager

A class-based implementation following SOLID principles for managing Azure Load Testing resources.
Uses Azure CLI authentication for simplicity and security.

Author: OSDU Performance Testing Team
Date: September 2025
"""

import logging
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from pathlib import Path
from azure.identity import AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.loadtesting import LoadTestMgmtClient
from azure.developer.loadtesting import LoadTestAdministrationClient, LoadTestRunClient

# Handle both relative imports (when used as module) and direct imports (when run as script)
try:
    from .resource_manager import AzureLoadTestResourceManager
    from .config import AzureLoadTestConfig
    from .file_manager import AzureLoadTestFileManager
    from .test_executor import AzureLoadTestExecutor
    from .entitlement_manager import AzureLoadTestEntitlementManager
except ImportError:
    from resource_manager import AzureLoadTestResourceManager
    from config import AzureLoadTestConfig
    from file_manager import AzureLoadTestFileManager
    from test_executor import AzureLoadTestExecutor
    from entitlement_manager import AzureLoadTestEntitlementManager


class UrllibResponse:
    """Compatibility wrapper for urllib responses to match requests.Response interface."""
    
    def __init__(self, status_code: int, content: bytes, headers: Optional[Dict] = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.text = content.decode('utf-8') if content else ''
    
    def json(self):
        """Parse response content as JSON."""
        return json.loads(self.text) if self.text else {}
    
    def raise_for_status(self):
        """Raise an exception for bad status codes."""
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP {self.status_code}: {self.text}")


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
                 tags: Optional[Dict[str, str]] = None,
                 test_runid_name: str = "osdu-perf-test",
                 allow_resource_creation: bool = False):
        
        """
        Initialize the Azure Load Test Manager.
        
        Args:
            subscription_id: Azure subscription ID
            resource_group_name: Resource group name
            load_test_name: Name for the load test resource
            location: Azure region (default: "eastus")
            tags: Dictionary of tags to apply to resources
        """
        # Initialize logger first
        self._setup_logging()
        
        # Initialize Azure credential
        self._credential = AzureCliCredential()
        
        # Create configuration object
        self.config = AzureLoadTestConfig(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            load_test_name=load_test_name,
            location=location,
            tags=tags or {"Environment": "Performance Testing", "Service": "OSDU"},
            test_runid_name=test_runid_name
        )
        
        # Store commonly used config values
        self.subscription_id = self.config.subscription_id
        self.resource_group_name = self.config.resource_group_name
        self.load_test_name = self.config.load_test_name
        self.location = self.config.location
        self.tags = self.config.tags
        self.test_runid_name = self.config.test_runid_name
        self.management_base_url = self.config.management_base_url
        self.api_version = self.config.api_version
        
        # Initialize Azure SDK clients (will be set after resource creation)
        self.loadtest_admin_client = None
        self.loadtest_run_client = None
        
        # Initialize Resource Manager for resource lifecycle operations
        self.allow_resource_creation = bool(allow_resource_creation)
        self.resource_manager = AzureLoadTestResourceManager(
            subscription_id=self.config.subscription_id,
            resource_group_name=self.config.resource_group_name,
            load_test_name=self.config.load_test_name,
            location=self.config.location,
            credential=self._credential,
            tags=self.config.tags,
            logger=self.logger,
            allow_resource_creation=self.allow_resource_creation,
        )
        
        # Log initialization
        self.logger.info(f"Azure Load Test Manager initialized {load_test_name}")
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
                '%(asctime)s - %(name)s -  %(filename)s:%(funcName)s:%(lineno)d - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _convert_time_to_seconds(self, time_str: str) -> int:
        """
        Convert time string to seconds for Azure Load Testing.
        
        Args:
            time_str: Time string like "60s", "5m", "1h", or just "60"
            
        Returns:
            int: Time in seconds
        """
        if not time_str:
            return 60  # Default to 60 seconds
            
        time_str = str(time_str).strip().lower()
        
        # If it's already just a number, assume seconds
        if time_str.isdigit():
            return int(time_str)
        
        # Parse time with units
        import re
        match = re.match(r'^(\d+)([smh]?)$', time_str)
        if not match:
            self.logger.warning(f"Invalid time format '{time_str}', defaulting to 60 seconds")
            return 60
            
        value, unit = match.groups()
        value = int(value)
        
        if unit == 's' or unit == '':  # seconds (default)
            return value
        elif unit == 'm':  # minutes
            return value * 60
        elif unit == 'h':  # hours
            return value * 3600
        else:
            self.logger.warning(f"Unknown time unit '{unit}', defaulting to 60 seconds")
            return 60
    
    def _initialize_credential(self) -> AzureCliCredential:
        """Initialize Azure CLI credential."""
        try:
            credential = AzureCliCredential()
            self.logger.info("✅ Azure CLI credential initialized successfully")
            return credential
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Azure CLI credential: {e}")
            raise
    
    def _init_data_plane_client(self, data_plane_uri: str, principal_id: str) -> None:
        """Initialize the data plane client after resource creation."""
        self.principal_id = principal_id
        try:
            if data_plane_uri:
                # Initialize Load Testing Clients for data plane operations
                self.loadtest_admin_client = LoadTestAdministrationClient(
                    endpoint=data_plane_uri,
                    credential=self._credential
                )
                
                self.loadtest_run_client = LoadTestRunClient(
                    endpoint=data_plane_uri,
                    credential=self._credential
                )

                self.logger.info(f"Data plane clients initialized: {data_plane_uri}")
                if "https://" not in data_plane_uri:
                    data_plane_uri = "https://" + data_plane_uri
                self.data_plane_url = data_plane_uri
                
                # Update configuration with data plane info
                self.config.update_data_plane_info(data_plane_uri, principal_id)
                
                # Initialize manager components that depend on data plane clients
                self.file_manager = AzureLoadTestFileManager(
                    loadtest_admin_client=self.loadtest_admin_client,
                    api_version=self.config.api_version,
                    logger=self.logger
                )
                
                self.test_executor = AzureLoadTestExecutor(
                    loadtest_run_client=self.loadtest_run_client,
                    logger=self.logger
                )
                
                self.entitlement_manager = AzureLoadTestEntitlementManager(
                    credential=self._credential,
                    principal_id=principal_id,
                    logger=self.logger
                )
            else:
                raise ValueError("Data plane URI not available")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize data plane client using SDK: {e}")
            raise

    
    def create_resource_group(self) -> bool:
        """
        Create the resource group if it doesn't exist.
        Delegates to AzureLoadTestResourceManager.
        
        Returns:
            bool: True if resource group exists or was created successfully
        """
        return self.resource_manager.create_resource_group()
    

    
    def create_load_test_resource(self) -> Optional[Dict[str, Any]]:
        """
        Create the Azure Load Test resource.
        Delegates to AzureLoadTestResourceManager.
        
        Returns:
            Dict[str, Any]: The created load test resource data, or None if failed
        """
        # Use resource manager to create the resource
        resource_dict = self.resource_manager.create_load_test_resource()
        
        if resource_dict:
            # Initialize data plane client with the resource details
            data_plane_uri = resource_dict.get('data_plane_uri')
            principal_id = resource_dict.get('identity', {}).get('principal_id')
            
            if data_plane_uri and principal_id:
                self._init_data_plane_client(data_plane_uri, principal_id)
        
        return resource_dict


    def create_test(self, test_name: str, test_files: List[Path],
                   host: Optional[str] = None,
                   partition: Optional[str] = None, 
                   app_id: Optional[str] = None,
                   token: Optional[str] = None,
                   users: int = 10,
                   spawn_rate: int = 2,
                   run_time: str = "60s",
                   engine_instances: int = 1, tags: str = "", adme_token: Optional[str] = None,
                   test_description: str = "") -> Optional[Dict[str, Any]]:
        """
        Create a test using Azure Load Testing Data Plane API with OSDU-specific parameters.
        
        Args:
            test_name: Name of the test to create
            test_files: List of test files to upload with the test
            host: OSDU host URL (e.g., https://your-osdu-host.com)
            partition: OSDU data partition ID (e.g., opendes)
            app_id: Azure AD Application ID for OSDU authentication
            token: Bearer token for OSDU authentication
            users: Number of concurrent users for load test
            spawn_rate: User spawn rate per second
            run_time: Test duration (e.g., "60s", "5m", "1h")
            engine_instances: Number of Azure Load Testing engine instances
            
        Returns:
            Dict[str, Any]: The created test data, or None if failed
        """
        try:
            self.logger.info(f"Creating Locust test '{test_name}' using Data Plane API...")
            
            # Get data plane URL and token
            data_plane_url = self.data_plane_url
        
            # Step 1: Create test configuration using data plane API
            url = f"{data_plane_url}/tests/{test_name}?api-version={self.api_version}"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/merge-patch+json"
            }
            
            # Locust test configuration
            # Ensure displayName is within 2-50 character limit
            display_name = test_name
            if len(display_name) > 50:
                display_name = test_name[:50]  # Keep within 50 char limit
            
            # Build environment variables for OSDU configuration
            environment_variables = {}
            secrets = {}
            
            # OSDU Configuration Parameters using Locust convention
            if host:
                environment_variables["LOCUST_HOST"] = host
            if partition:
                environment_variables["PARTITION"] = partition
            if app_id:
                environment_variables["APPID"] = app_id

            # Load Test Parameters - convert run_time to seconds integer
            environment_variables["LOCUST_USERS"] = str(users)
            environment_variables["LOCUST_SPAWN_RATE"] = str(spawn_rate)
            environment_variables["LOCUST_RUN_TIME"] = str(self._convert_time_to_seconds(run_time))
            environment_variables["AZURE_LOAD_TEST"] = "true"
            
            # Additional OSDU-specific environment variables that tests might need
            environment_variables["OSDU_ENV"] = "performance_test"
            environment_variables["OSDU_TENANT_ID"] = partition if partition else "opendes"
            environment_variables["TEST_RUN_ID_NAME"] = self.test_runid_name
            environment_variables["LOCUST_TAGS"] = tags 
            environment_variables["ADME_BEARER_TOKEN"] = adme_token  # Pass the token for authentication 
            environment_variables["LAST_TEST_TIME_STAMP"] = str(int(time.time()))  # Unique test iteration based on timestamp

            
            body = {
                "displayName": display_name,
                "description": test_description if test_description else f"Load test for {test_name}",
                "kind": "Locust",  # Specify Locust as the testing framework
                "engineBuiltinIdentityType": "SystemAssigned",
                "loadTestConfiguration": {
                    "engineInstances": engine_instances,
                    "splitAllCSVs": False,
                    "quickStartTest": False
                },
                "passFailCriteria": {
                    "passFailMetrics": {}
                },
                "environmentVariables": environment_variables,
                "secrets": secrets
            }
            
           
            
            # Convert to JSON string
            json_payload = json.dumps(body).encode('utf-8')
            
            # Create urllib request
            req = urllib.request.Request(url, data=json_payload, method='PATCH')
            
            # Add headers
            for key, value in headers.items():
                req.add_header(key, value)
            
            # Make the request
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    response_status = response.getcode()
                    response_data = response.read().decode('utf-8')
                    response_headers = dict(response.headers)
                    
                # Create a response-like object for compatibility
                response = UrllibResponse(response_status, response_data.encode('utf-8'), response_headers)
                
            except urllib.error.HTTPError as e:
                error_content = e.read() if hasattr(e, 'read') else b''
                response = UrllibResponse(e.code, error_content, dict(e.headers) if hasattr(e, 'headers') else {})
            
            # Debug response
            self.logger.info(f"Test creation response status: {response.status_code}")
            if response.status_code not in [200, 201]:
                self.logger.error(f"Response headers: {dict(response.headers)}")
                self.logger.error(f"Response text: {response.text}")

            response.raise_for_status()
            
            test_result = response.json() if response.content else {}
            self.logger.info(f"Locust test '{test_name}' created successfully")
            return test_result
                
        except Exception as e:
            self.logger.error(f"Error creating test '{test_name}': {e}")
            return None

    
    def get_data_plane_token(self) -> str:
        """Get Azure Load Testing data plane access token."""
        try:
            self.logger.info(f"Acquiring data plane access token...")
            # Use the same credential but with data plane scope
            token = self._credential.get_token("https://cnt-prod.loadtesting.azure.com/.default")
            return token.token
        except Exception as e:
            self.logger.error(f"Failed to get data plane access token: {e}")
            # Fallback to management token if data plane scope fails
            return None

    def get_management_token(self) -> str:
        """Get Azure Load Testing management access token."""
        try:
            self.logger.info(f"Acquiring management access token...")
            token = self._credential.get_token("https://management.azure.com/.default")
            return token.token
        except Exception as e:
            self.logger.error(f"Failed to get management access token: {e}")
            return None

    def _upload_files_for_test_dataplane(self, test_name: str, test_files: List[Path], data_plane_url: str, data_plane_token: str) -> List[Dict[str, Any]]:
        """
        Upload test files to Azure Load Testing using Data Plane API.
        Delegates to AzureLoadTestFileManager.
        
        Args:
            test_name: Name of the test 
            test_files: List of test files to upload
            data_plane_url: Data plane URL from management API
            data_plane_token: Data plane authentication token
            
        Returns:
            List[Dict[str, Any]]: List of uploaded file information
        """
        if not hasattr(self, 'file_manager') or not self.file_manager:
            raise ValueError("File manager not initialized. Create load test resource first.")
        
        return self.file_manager.upload_files_for_test(test_name, test_files)

    def create_tests_and_upload_test_files(self, test_name: str, test_directory: str = '.', 
                        host: Optional[str] = None,
                        partition: Optional[str] = None,
                        app_id: Optional[str] = None, 
                        users: int = 10,
                        spawn_rate: int = 2,
                        run_time: str = "60s",
                        engine_instances: int = 1,
                        tags: str = "", adme_token: Optional[str] = None,
                        test_description: str = "") -> bool:
        """
        Complete test files setup: find, copy, and upload test files to Azure Load Test resource.
        Delegates file finding and uploading to AzureLoadTestFileManager.
        
        Args:
            test_name: Name of the test for directory creation
            test_directory: Directory to search for test files
            host: OSDU host URL (e.g., https://your-osdu-host.com)
            partition: OSDU data partition ID (e.g., opendes)
            app_id: Azure AD Application ID for OSDU authentication
            token: Bearer token for OSDU authentication
            users: Number of concurrent users for load test
            spawn_rate: User spawn rate per second
            run_time: Test duration (e.g., "60s", "5m", "1h")
            engine_instances: Number of Azure Load Testing engine instances
            
        Returns:
            bool: True if setup completed successfully
        """
        import os
        
        try:
            # Verify file_manager is initialized
            if not hasattr(self, 'file_manager') or not self.file_manager:
                raise ValueError("File manager not initialized. Create load test resource first.")
            
            # Use file_manager to find test files
            test_files = self.file_manager.find_test_files(test_directory)
            
            # Filter out config files (security: exclude sensitive configuration)
            config_files_to_exclude = ['config.yaml', 'config.yml', '.env', '.config']
            filtered_test_files = []
            excluded_files = []
            
            for file_path in test_files:
                file_name = os.path.basename(file_path)
                if any(config_name in file_name.lower() for config_name in config_files_to_exclude):
                    excluded_files.append(file_name)
                else:
                    filtered_test_files.append(file_path)
            
            test_files = filtered_test_files
            
            if excluded_files:
                self.logger.info(f"🔒 Excluded config files (security): {', '.join(excluded_files)}")
            
            if not test_files:
                self.logger.error("❌ No test files found!")
                self.logger.error("   Make sure you have performance test files in one of these patterns:")
                self.logger.error("   - perf_storage_test.py")
                self.logger.error("   - perf_search_test.py")
                self.logger.error("   - locustfile.py (optional, will use OSDU default if not found)")
                self.logger.error("   - requirements.txt ")
                return False

            self.logger.info(f"Found {len(test_files)} performance test files")
            self.logger.info("Files to upload to Azure Load Testing:")
            for test_file in test_files:
                file_name = os.path.basename(test_file)
                self.logger.info(f"   • {file_name}")
            self.logger.info("")
            
            # Convert file paths to Path objects for the new workflow
            path_objects = [Path(f) for f in test_files]
            
            # Create the test with files using the new Azure Load Testing workflow
            self.logger.info("")
            self.logger.info(f"🧪 Creating test '{test_name}' with files and OSDU configuration...")
            self.logger.info(f"   Host: {host or 'Not provided'}")
            self.logger.info(f"   Partition: {partition or 'Not provided'}")
            self.logger.info(f"   Users: {users}")
            self.logger.info(f"   Spawn Rate: {spawn_rate}/sec")
            self.logger.info(f"   Run Time: {run_time}")
            self.logger.info(f"   Engine Instances: {engine_instances}")
            self.logger.info(f"   Test Scenario tags: {tags}")
            
            data_plane_token = self.get_data_plane_token()
            if not data_plane_token:
                self.logger.error("Failed to acquire data plane token")
                return False
            
            test_result = self.create_test(
                test_name=test_name, 
                test_files=path_objects,
                host=host,
                partition=partition, 
                app_id=app_id,
                token=data_plane_token,
                users=users,
                spawn_rate=spawn_rate,
                run_time=run_time,
                engine_instances=engine_instances,
                tags=tags,
                adme_token=adme_token,
                test_description=test_description,
            )
            
            if not test_result:
                self.logger.error("Failed to create test in Azure Load Test resource")
                return False
            
            self.logger.info(f"Test '{test_name}' created successfully")
            
            # Upload test files using file_manager (delegates to AzureLoadTestFileManager)
            self.logger.info(f"📤 Uploading {len(test_files)} test files using File Manager...")
            uploaded_files = self.file_manager.upload_files_for_test(test_name, path_objects)
            
            if uploaded_files:
                self.logger.info(f"✅ Successfully uploaded {len(uploaded_files)} files")
            else:
                self.logger.warning(f"⚠️ No files were uploaded")

            self.logger.info(f"✅ Test '{test_name}' created and files uploaded successfully!")

            self.logger.info("")
            self.logger.info(f"Test Resource: {self.load_test_name}")
            self.logger.info(f"Test Name: {test_name}")
            self.logger.info(f"Resource Group: {self.resource_group_name}")
            self.logger.info(f"Location: {self.location}")
            self.logger.info(f"Test Type: Locust")
            self.logger.info(f"Azure Load Testing Portal:")
            self.logger.info(f"  https://portal.azure.com/#@{self.subscription_id}/resource/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group_name}/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up test files: {e}")
            return False

    def run_test(self, test_name: str, display_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Start a test execution using Azure Load Testing Data Plane API.
        Delegates to AzureLoadTestExecutor.
        
        Args:
            test_name: Name of the test to run
            display_name: Display name for the test run (optional)
            
        Returns:
            Dict[str, Any]: The test execution data, or None if failed
        """
        if not hasattr(self, 'test_executor') or not self.test_executor:
            raise ValueError("Test executor not initialized. Create load test resource first.")
        
        return self.test_executor.run_test(test_name, display_name)
       
    def get_app_id_from_principal_id(self, principal_id: str) -> str:
        """
        Get App ID from Object (principal) ID using Microsoft Graph API.
        Delegates to AzureLoadTestEntitlementManager.
        
        Args:
            principal_id: The Object (principal) ID
            
        Returns:
            The application ID
        """
        if not hasattr(self, 'entitlement_manager') or not self.entitlement_manager:
            raise ValueError("Entitlement manager not initialized. Create load test resource first.")
        
        return self.entitlement_manager.get_app_id_from_principal_id(principal_id)

    def setup_load_test_entitlements(self, load_test_name: str, host: str, partition: str, osdu_adme_token: str) -> bool:
        """
        Set up entitlements for a load test application.
        Delegates to AzureLoadTestEntitlementManager.
        
        This function:
        1. Resolves the app ID from the load test name
        2. Creates an Entitlement object with OSDU configuration
        3. Creates entitlements for the load test app
        
        Args:
            load_test_name: Name of the load test instance
            host: OSDU host URL (e.g., https://your-osdu-host.com)
            partition: OSDU data partition ID (e.g., opendes)
            osdu_adme_token: Bearer token for OSDU authentication
            
        Returns:
            bool: True if entitlements were set up successfully
        """
        if not hasattr(self, 'entitlement_manager') or not self.entitlement_manager:
            raise ValueError("Entitlement manager not initialized. Create load test resource first.")
        
        return self.entitlement_manager.setup_load_test_entitlements(
            load_test_name=load_test_name,
            host=host,
            partition=partition,
            osdu_adme_token=osdu_adme_token
        )


def main():
    """
    Example usage of the AzureLoadTestManager class.
    """
    # Configuration
    SUBSCRIPTION_ID = "015ab1e4-bd82-4c0d-ada9-0f9e9c68e0c4"
    RESOURCE_GROUP = "janrajcj-rg-test"
    LOAD_TEST_NAME = "janraj-loadtest-instance"
    LOCATION = "eastus"
    
    # Setup logging for demo
    import logging
    demo_logger = logging.getLogger("AzureLoadTestDemo")
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    demo_logger.addHandler(handler)
    demo_logger.setLevel(logging.INFO)
    
    try:
        demo_logger.info("Azure Load Test Manager")
        demo_logger.info("=" * 60)

        # Initialize the runner
        runner = AzureLoadTestRunner(
            subscription_id=SUBSCRIPTION_ID,
            resource_group_name=RESOURCE_GROUP,
            load_test_name=LOAD_TEST_NAME,
            location=LOCATION,
            tags={"Environment": "Demo", "Project": "OSDU"},
        )
        
        # Create the load test 
        load_test = runner.create_load_test_resource()
        
        if load_test:
            demo_logger.info(f"[main] Load Testing instance created: {load_test['id']}")
            
            import pdb
            pdb.set_trace()
            # Create test and upload test files
            demo_logger.info("=" * 60)
            demo_logger.info("[main] Creating test and uploading files...")
            
            test_created = runner.create_tests_and_upload_test_files(
                test_name="demo_test",
                test_directory="./perf_tests",
                host="https://demo-osdu-host.com",
                partition="opendes",
                app_id="demo-app-id",
                users=5,
                spawn_rate=1,
                run_time="30s",
                engine_instances=1,
                tags="demo",
                adme_token="demo-token"
            )
            
            if test_created:
                demo_logger.info("[main] Test created and files uploaded successfully!")
            else:
                demo_logger.warning("[main] Test creation or file upload failed (this is expected if ./perf_tests doesn't exist)")
        
        demo_logger.info("=" * 60)
        demo_logger.info("[main] Azure Load Test Manager execution completed successfully!")
        
    except Exception as e:
        demo_logger.error(f"[main] Error: {e}")
        demo_logger.error("\n[main] Troubleshooting:")
        demo_logger.error("1. Ensure Azure CLI is installed: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")
        demo_logger.error("2. Login to Azure CLI: az login")
        demo_logger.error("3. Verify subscription: az account show")
        demo_logger.error("4. Check permissions for creating resources")

if __name__ == "__main__":
    main()