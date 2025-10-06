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
import re
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
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
    
    def _get_data_plane_token(self) -> str:
        """
        Get a token for data plane access.
        Data plane accepts management tokens, so we can reuse the existing token.
        
        Returns:
            str: Authentication token for data plane access
        """
        try:
            # Get management token - data plane accepts these tokens
            token = self._get_access_token()
            self.logger.debug(f"🔐 Using management token for data plane access")
            return token
        except Exception as e:
            self.logger.error(f"❌ Failed to get data plane access token: {e}")
            # Fallback to management token if data plane scope fails
            return self._get_access_token()

    def _get_access_token(self, resource: str = "https://management.azure.com/.default") -> str:
        """
        Get Azure API access token for specified resource.
        
        Args:
            resource: The resource URL to get token for (default: Azure Management API)
        
        Returns:
            str: Access token
        """
        try:
            token = self._credential.get_token(resource)
            return token.token
        except Exception as e:
            self.logger.error(f"❌ Failed to get access token for {resource}: {e}")
            raise
    
    def _get_token(self) -> str:
        """Alias for _get_access_token for compatibility."""
        return self._get_access_token()
    
    def _get_data_plane_url(self) -> str:
        """Get the data plane URL from the Load Testing resource."""
        try:
            url = (f"{self.management_base_url}/subscriptions/{self.subscription_id}/"
                  f"resourceGroups/{self.resource_group_name}/"
                  f"providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}"
                  f"?api-version=2022-12-01")
            
            headers = {"Authorization": f"Bearer {self._get_token()}"}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            properties = response.json().get("properties", {})
            data_plane_uri = properties.get("dataPlaneURI")
            
            if not data_plane_uri:
                raise ValueError("Data plane URI not found in Load Testing resource")
            
            # Ensure the URL has https:// scheme
            if not data_plane_uri.startswith("https://"):
                data_plane_uri = f"https://{data_plane_uri}"
            
            self.logger.info(f"Data plane URI: {data_plane_uri}")
            return data_plane_uri
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get data plane URL: {e}")
            raise
    
    def _get_data_plane_token(self) -> str:
        """Get data plane specific token."""
        try:
            # Try data plane scope first
            token = self._credential.get_token("https://cnt-prod.loadtesting.azure.com/.default")
            return token.token
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to get data plane token: {e}, using management token")
            # Fallback to management token
            return self._get_access_token()
    
    def create_or_get_load_test(self) -> Optional[Dict[str, Any]]:
        """
        Create or get existing Azure Load Test resource.
        
        Returns:
            Dict[str, Any]: Load test resource data, or None if failed
        """
        try:
            # First check if it exists
            existing = self.get_load_test()
            if existing:
                self.logger.info(f"✅ Load test resource '{self.load_test_name}' already exists")
                return existing
                
            # Create new resource
            self.logger.info(f"🏗️  Creating load test resource '{self.load_test_name}'...")
            return self.create_load_test()
            
        except Exception as e:
            self.logger.error(f"❌ Error creating or getting load test resource: {e}")
            return None
    
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

    def create_test(self, test_name: str, test_files: List[Path], 
                   host: Optional[str] = None,
                   partition: Optional[str] = None, 
                   app_id: Optional[str] = None,
                   token: Optional[str] = None,
                   users: int = 10,
                   spawn_rate: int = 2,
                   run_time: str = "60s",
                   engine_instances: int = 1) -> Optional[Dict[str, Any]]:
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
            self.logger.info(f"🧪 Creating Locust test '{test_name}' using Data Plane API...")
            
            # Get data plane URL and token
            data_plane_url = self._get_data_plane_url()
            data_plane_token = self._get_data_plane_token()
            
            # Step 1: Create test configuration using data plane API
            url = f"{data_plane_url}/tests/{test_name}?api-version={self.api_version}"
            
            headers = {
                "Authorization": f"Bearer {data_plane_token}",
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
            
            body = {
                "displayName": display_name,
                "description": f"Load test for OSDU performance using Locust framework - {users} users, {spawn_rate} spawn rate, {run_time} duration",
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
            
            # Create the test
            response = requests.patch(url, headers=headers, json=body, timeout=30)
            
            # Debug response
            self.logger.info(f"Test creation response status: {response.status_code}")
            if response.status_code not in [200, 201]:
                self.logger.error(f"Response headers: {dict(response.headers)}")
                self.logger.error(f"Response text: {response.text}")
                
            response.raise_for_status()
            
            test_result = response.json() if response.content else {}
            self.logger.info(f"✅ Locust test '{test_name}' created successfully")
            

            # Step 2: Upload test files using data plane API
            uploaded_files = self._upload_files_for_test_dataplane(test_name, test_files, data_plane_url, data_plane_token)
            if uploaded_files:
                self.logger.info(f"✅ Successfully uploaded {len(uploaded_files)} files")
            
            return test_result
                
        except Exception as e:
            self.logger.error(f"❌ Error creating test '{test_name}': {e}")
            return None

    def _get_data_plane_token(self) -> str:
        """Get Azure Load Testing data plane access token."""
        try:
            # Use the same credential but with data plane scope
            token = self._credential.get_token("https://cnt-prod.loadtesting.azure.com/.default")
            return token.token
        except Exception as e:
            self.logger.error(f"❌ Failed to get data plane access token: {e}")
            # Fallback to management token if data plane scope fails
            return self._get_access_token()

    def _upload_files_for_test(self, test_files: List[Path]) -> List[Dict[str, Any]]:
        """
        Upload test files using the Azure Load Testing file upload workflow:
        1. POST to create file metadata and get blob storage URL
        2. PUT file content to blob storage
        
        Args:
            test_files: List of test files to upload
            
        Returns:
            List[Dict[str, Any]]: List of uploaded file information
        """
        try:
            self.logger.info(f"📁 Uploading {len(test_files)} test files using Azure Load Testing workflow...")
            
            uploaded_files = []
            headers = {
                "Authorization": f"Bearer {self._get_token()}",
                "Content-Type": "application/json"
            }
            
            for file_path in test_files:
                try:
                    # Step 1: Create file metadata and get blob storage URL
                    file_type = "testScript" if re.match(r'perf_.*test\.py$', file_path.name) else "additionalScript"
                    
                    file_metadata = {
                        "fileName": file_path.name
                    }
                    
                    files_url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group_name}/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}/files?api-version=2022-12-01"
                    
                    response = requests.post(files_url, headers=headers, json=file_metadata, timeout=30)
                    
                    if response.status_code not in [200, 201]:
                        self.logger.error(f"❌ Failed to create file metadata for {file_path.name}: {response.status_code} - {response.text}")
                        continue
                    
                    file_info = response.json()
                    
                    # Step 2: Upload file content to blob storage URL
                    blob_url = file_info.get('properties', {}).get('uploadBlobUrl')
                    if not blob_url:
                        self.logger.error(f"❌ No blob upload URL received for {file_path.name}")
                        continue
                    
                    with open(file_path, 'rb') as f:
                        blob_headers = {
                            "Content-Type": "application/octet-stream",
                            "x-ms-blob-type": "BlockBlob"
                        }
                        
                        blob_response = requests.put(blob_url, headers=blob_headers, data=f, timeout=60)
                    
                    if blob_response.status_code in [200, 201]:
                        self.logger.info(f"✅ Uploaded {file_path.name}")
                        uploaded_files.append({
                            "fileName": file_path.name,
                            "fileType": file_type,
                            "fileInfo": file_info
                        })
                    else:
                        self.logger.error(f"❌ Failed to upload {file_path.name} to blob storage: {blob_response.status_code}")
                        
                except Exception as file_error:
                    self.logger.error(f"❌ Error uploading {file_path.name}: {file_error}")
            
            if uploaded_files:
                self.logger.info(f"✅ Successfully uploaded {len(uploaded_files)} files")
                return uploaded_files
            else:
                self.logger.error("❌ No files were uploaded successfully")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading files: {e}")
            return []

    def _upload_files_for_test_dataplane(self, test_name: str, test_files: List[Path], data_plane_url: str, data_plane_token: str) -> List[Dict[str, Any]]:
        """
        Upload test files to Azure Load Testing using Data Plane API (following samplejan.py approach).
        
        Args:
            test_name: Name of the test 
            test_files: List of test files to upload
            data_plane_url: Data plane URL from management API
            data_plane_token: Data plane authentication token
            
        Returns:
            List[Dict[str, Any]]: List of uploaded file information
        """
        uploaded_files = []
        
        try:
            for file_path in test_files:
                if not file_path.exists():
                    self.logger.warning(f"⚠️ File does not exist: {file_path}")
                    continue
                    
                self.logger.info(f"📁 Uploading file: {file_path.name}")
                
                # Determine file type - Locust scripts should use JMX_FILE type
                # JMX_FILE: Main test scripts locustfile.py
                # ADDITIONAL_ARTIFACTS: Supporting files (requirements.txt, utilities, perf.*test.py)
                if file_path.name.lower() == 'locustfile.py':
                    file_type = "JMX_FILE"  # Main Locust configuration file
                else:
                    file_type = "ADDITIONAL_ARTIFACTS"  # All other files (requirements.txt, perf_.*_test.py)
                
                # Upload file using direct data plane API
                url = f"{data_plane_url}/tests/{test_name}/files/{file_path.name}?api-version={self.api_version}&fileType={file_type}"
                
                headers = {
                    "Authorization": f"Bearer {data_plane_token}",
                    "Content-Type": "application/octet-stream"
                }
                
                # Read and upload file content
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                response = requests.put(url, headers=headers, data=file_content, timeout=60)
                
                # Debug response
                self.logger.info(f"File upload response status for {file_path.name}: {response.status_code}")
                
                if response.status_code not in [200, 201]:
                    self.logger.error(f"Response headers: {dict(response.headers)}")
                    self.logger.error(f"Response text: {response.text}")
                    continue
                
                response.raise_for_status()
                
                file_info = {
                    "fileName": file_path.name,
                    "fileType": file_type,
                    "uploadStatus": "success"
                }
                uploaded_files.append(file_info)
                self.logger.info(f"✅ Successfully uploaded: {file_path.name} as {file_type}")
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading files: {e}")
            
        return uploaded_files

    def setup_test_files(self, test_name: str, test_directory: str = '.', 
                        host: Optional[str] = None,
                        partition: Optional[str] = None,
                        app_id: Optional[str] = None, 
                        token: Optional[str] = None,
                        users: int = 10,
                        spawn_rate: int = 2,
                        run_time: str = "60s",
                        engine_instances: int = 1) -> bool:
        """
        Complete test files setup: find, copy, and upload test files to Azure Load Test resource.
        
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
        import shutil
        import glob
        
        try:
            self.logger.info(f"🔍 Searching for test files in: {test_directory}")
            
            # Search patterns for performance test files and locustfile
            search_patterns = [
                os.path.join(test_directory, "perf_*_test.py"),
                os.path.join(test_directory, "**", "perf_*_test.py"),
                os.path.join(test_directory, "perf_*test.py"),
                os.path.join(test_directory, "**", "perf_*test.py"),
                os.path.join(test_directory, "locustfile.py"),
                os.path.join(test_directory, "requirements.txt"),
                os.path.join(test_directory, "config.yaml")
            ]
            
            test_files = []
            for pattern in search_patterns:
                found_files = glob.glob(pattern, recursive=True)
                test_files.extend(found_files)
            
            # If no locustfile.py found in user directory, copy the OSDU library version
            has_locustfile = any('locustfile.py' in f for f in test_files)
            if not has_locustfile:
                self.logger.info("🔍 No locustfile.py found in test directory, using OSDU library version...")
                try:
                    import pkg_resources
                    # Try to find the OSDU locustfile.py from the package
                    osdu_locustfile = pkg_resources.resource_filename('osdu_perf.core', 'locustfile.py')
                    if os.path.exists(osdu_locustfile):
                        test_files.append(osdu_locustfile)
                        self.logger.info(f"   ✅ Added OSDU locustfile.py: {osdu_locustfile}")
                except (ImportError, Exception) as e:
                    self.logger.warning(f"   ⚠️  Could not find OSDU locustfile.py: {e}")
                    # Fallback: look for it in the same directory as this file
                    current_dir = os.path.dirname(__file__)
                    fallback_locustfile = os.path.join(current_dir, 'locustfile.py')
                    if os.path.exists(fallback_locustfile):
                        test_files.append(fallback_locustfile)
                        self.logger.info(f"   ✅ Added fallback locustfile.py: {fallback_locustfile}")
                    else:
                        self.logger.warning(f"   ⚠️  No locustfile.py found, tests may need manual configuration")
            
            # Remove duplicates and sort
            test_files = sorted(list(set(test_files)))
            
            if not test_files:
                self.logger.error("❌ No test files found!")
                self.logger.error("   Make sure you have performance test files in one of these patterns:")
                self.logger.error("   - perf_storage_test.py")
                self.logger.error("   - perf_search_test.py")
                self.logger.error("   - locustfile.py (optional, will use OSDU default if not found)")
                self.logger.error("   - requirements.txt ")
                return False
            
            self.logger.info(f"✅ Found {len(test_files)} performance test files:")
            for test_file in test_files:
                rel_path = os.path.relpath(test_file, test_directory)
                self.logger.info(f"   • {rel_path}")
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
            
            test_result = self.create_test(
                test_name=test_name, 
                test_files=path_objects,
                host=host,
                partition=partition, 
                app_id=app_id,
                token=token,
                users=users,
                spawn_rate=spawn_rate,
                run_time=run_time,
                engine_instances=engine_instances
            )
            if not test_result:
                self.logger.error("❌ Failed to create test in Azure Load Test resource")
                return False
            
            self.logger.info(f"✅ Test '{test_name}' created and files uploaded successfully!")
            self.logger.info("🔧 Test is ready with Locust engine type")
            
            self.logger.info("")
            self.logger.info(f"📊 Test Resource: {self.load_test_name}")
            self.logger.info(f"🧪 Test Name: {test_name}")
            self.logger.info(f"🌐 Resource Group: {self.resource_group_name}")
            self.logger.info(f"📍 Location: {self.location}")
            self.logger.info(f"🧪 Test Type: Locust")
            self.logger.info("🔗 Azure Load Testing Portal:")
            self.logger.info(f"   https://portal.azure.com/#@{self.subscription_id}/resource/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group_name}/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error setting up test files: {e}")
            return False

    def upload_test_files_to_test(self, test_name: str, test_files: List[str]) -> bool:
        """
        Upload test files to a specific test within the Azure Load Test resource.
        
        Args:
            test_name: Name of the test to upload files to
            test_files: List of absolute file paths to upload
            
        Returns:
            bool: True if all files uploaded successfully
        """
        try:
            if not test_files:
                self.logger.warning("⚠️ No test files provided for upload")
                return True
            
            self.logger.info(f"📁 Uploading {len(test_files)} test files to test '{test_name}'...")
            
            # Get the data plane URI for file uploads
            load_test_info = self.get_load_test()
            if not load_test_info:
                self.logger.error("❌ Load test resource not found for file upload")
                return False
                
            data_plane_uri = load_test_info.get('properties', {}).get('dataPlaneURI')
            if not data_plane_uri:
                self.logger.error("❌ Data plane URI not available for file upload")
                return False
            
            upload_success = True
            for file_path in test_files:
                if self._upload_single_file_to_test(test_name, file_path, data_plane_uri):
                    self.logger.info(f"   ✅ Uploaded: {file_path}")
                else:
                    self.logger.error(f"   ❌ Failed to upload: {file_path}")
                    upload_success = False
            
            if upload_success:
                self.logger.info("✅ All test files uploaded successfully")
                # Update test configuration with the uploaded files
                self._update_test_configuration(test_name, test_files)
            else:
                self.logger.error("❌ Some files failed to upload")
                
            return upload_success
            
        except Exception as e:
            self.logger.error(f"❌ Error uploading test files to test '{test_name}': {e}")
            return False

    def _wait_for_test_validation(self, test_name: str, max_wait_time: int = 300) -> bool:
        """
        Wait for test script validation to complete before starting execution.
        
        Args:
            test_name: Name of the test to check
            max_wait_time: Maximum time to wait in seconds (default: 5 minutes)
            
        Returns:
            bool: True if validation completed successfully, False if timeout or error
        """
        try:
            self.logger.info(f"⏳ Checking test script validation status for '{test_name}'...")
            
            # Get data plane URL and token
            data_plane_url = self._get_data_plane_url()
            data_plane_token = self._get_data_plane_token()
            
            # Check test status URL
            test_status_url = f"{data_plane_url}/tests/{test_name}?api-version={self.api_version}"
            
            headers = {
                "Authorization": f"Bearer {data_plane_token}",
                "Content-Type": "application/json"
            }
            
            start_time = time.time()
            wait_interval = 10  # Check every 10 seconds
            
            while (time.time() - start_time) < max_wait_time:
                try:
                    response = requests.get(test_status_url, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        test_data = response.json()
                        
                        # Check if test has valid script files
                        input_artifacts = test_data.get('inputArtifacts', {})
                        test_script_file = input_artifacts.get('testScriptFileInfo', {})
                        
                        # Check if validation is complete (file exists and has validation info)
                        if test_script_file and test_script_file.get('fileName'):
                            validation_status = test_script_file.get('validationStatus')
                            validation_failure_details = test_script_file.get('validationFailureDetails')
                            
                            if validation_status == 'VALIDATION_SUCCESS':
                                self.logger.info(f"✅ Test script validation completed successfully for '{test_name}'")
                                return True
                            elif validation_status == 'VALIDATION_FAILURE':
                                self.logger.error(f"❌ Test script validation failed: {validation_failure_details}")
                                return False
                            elif validation_status in ['VALIDATION_INITIATED', 'VALIDATION_IN_PROGRESS', None]:
                                self.logger.info(f"⏳ Test script validation in progress... (waiting {wait_interval}s)")
                            else:
                                self.logger.info(f"⏳ Test script validation status: {validation_status} (waiting {wait_interval}s)")
                        else:
                            self.logger.info(f"⏳ Test script not yet available for validation... (waiting {wait_interval}s)")
                    else:
                        self.logger.warning(f"⚠️ Could not check test status: {response.status_code}")
                
                except Exception as e:
                    self.logger.warning(f"⚠️ Error checking test validation status: {e}")
                
                # Wait before next check
                time.sleep(wait_interval)
            
            # Timeout reached
            elapsed_time = time.time() - start_time
            self.logger.warning(f"⚠️ Test script validation timeout after {elapsed_time:.0f} seconds")
            self.logger.info("📝 Proceeding with test execution anyway - validation may complete during execution")
            return True  # Return True to allow execution attempt
            
        except Exception as e:
            self.logger.error(f"❌ Error waiting for test validation: {e}")
            return True  # Return True to allow execution attempt

    def run_test(self, test_name: str, display_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Start a test execution using Azure Load Testing Data Plane API.
        
        Args:
            test_name: Name of the test to run
            display_name: Display name for the test run (optional)
            
        Returns:
            Dict[str, Any]: The test execution data, or None if failed
        """
        try:
            self.logger.info(f"🚀 Starting test execution for '{test_name}' using Data Plane API...")
            
            # Wait for test script validation to complete before starting execution
            if not self._wait_for_test_validation(test_name):
                self.logger.error(f"❌ Test script validation failed for '{test_name}'")
                return None
            
            # Get data plane URL and token
            data_plane_url = self._get_data_plane_url()
            data_plane_token = self._get_data_plane_token()
            
            # Create execution configuration with proper display name validation
            timestamp = int(time.time())
            
            # Ensure display name meets Azure Load Testing requirements (2-50 characters)
            if display_name:
                # Use provided display name but ensure it meets length requirements
                if len(display_name) < 2:
                    display_name = f"{display_name}-run"
                elif len(display_name) > 50:
                    display_name = display_name[:47] + "..."
            else:
                # Generate a display name that fits within limits
                base_name = test_name[:20] if len(test_name) > 20 else test_name
                display_name = f"{base_name}-{timestamp}"
                # Ensure it's within the 50 character limit
                if len(display_name) > 50:
                    # Truncate the base name to fit
                    max_base_length = 50 - len(f"-{timestamp}")
                    base_name = test_name[:max_base_length] if len(test_name) > max_base_length else test_name
                    display_name = f"{base_name}-{timestamp}"
            
            execution_config = {
                "displayName": display_name
            }
            
            self.logger.info(f"🏷️  Using display name: '{display_name}' (length: {len(display_name)})")
            
            # Start test execution using Data Plane API  
            execution_url = f"{data_plane_url}/test-runs/{test_name}-run-{timestamp}?api-version={self.api_version}"
            
            headers = {
                "Authorization": f"Bearer {data_plane_token}",
                "Content-Type": "application/merge-patch+json"
            }
            
            # Build the test run configuration
            test_run_config = {
                "testId": test_name,
                "displayName": execution_config["displayName"],
                "description": f"Load test execution for {test_name} via OSDU Performance Framework"
            }
            
            response = requests.patch(execution_url, headers=headers, json=test_run_config, timeout=30)
            
            # Debug response
            self.logger.info(f"Test execution response status: {response.status_code}")
            if response.status_code not in [200, 201]:
                self.logger.error(f"Response headers: {dict(response.headers)}")
                self.logger.error(f"Response text: {response.text}")
            
            if response.status_code in [200, 201]:
                result = response.json() if response.content else {}
                execution_id = result.get('testRunId', result.get('name', 'unknown'))
                self.logger.info(f"✅ Test execution started successfully - Execution ID: {execution_id}")
                return result
            elif response.status_code == 400:
                # Check if this is the validation error
                try:
                    error_response = response.json()
                    error_code = error_response.get('error', {}).get('code')
                    error_message = error_response.get('error', {}).get('message', '')
                    
                    if error_code == 'MissingValidatedTestScriptFile':
                        self.logger.warning(f"⚠️ Test script still being validated: {error_message}")
                        
                        # Retry the execution once more
                        self.logger.info("🔄 Retrying test execution after validation wait...")
                        retry_response = requests.patch(execution_url, headers=headers, json=test_run_config, timeout=30)
                        
                        if retry_response.status_code in [200, 201]:
                            result = retry_response.json() if retry_response.content else {}
                            execution_id = result.get('testRunId', result.get('name', 'unknown'))
                            self.logger.info(f"✅ Test execution started successfully on retry - Execution ID: {execution_id}")
                            return result
                        else:
                            self.logger.error(f"❌ Retry also failed: {retry_response.status_code} - {retry_response.text}")
                            return None
                    else:
                        self.logger.error(f"❌ Failed to start test execution: {response.status_code} - {response.text}")
                        return None
                except Exception as e:
                    self.logger.error(f"❌ Error parsing error response: {e}")
                    self.logger.error(f"❌ Failed to start test execution: {response.status_code} - {response.text}")
                    return None
            else:
                self.logger.error(f"❌ Failed to start test execution: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error starting test execution '{test_name}': {e}")
            return None

    def _upload_single_file_to_test(self, test_name: str, file_path: str, data_plane_uri: str) -> bool:
        """Upload a single test file to a specific test."""
        try:
            import os
            if not os.path.exists(file_path):
                self.logger.error(f"❌ File not found: {file_path}")
                return False
            
            file_name = os.path.basename(file_path)
            
            # Upload file to specific test
            upload_url = f"https://{data_plane_uri}/tests/{test_name}/files/{file_name}?api-version=2024-05-01-preview"
            
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Upload file
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream"
            }
            
            response = requests.put(upload_url, headers=headers, data=file_content, timeout=60)
            
            if response.status_code in [200, 201]:
                return True
            else:
                self.logger.error(f"❌ Upload failed for {file_name}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading file {file_path} to test {test_name}: {e}")
            return False

    def _update_test_configuration(self, test_name: str, test_files: List[str]) -> bool:
        """Update test configuration with uploaded files."""
        try:
            import os
            
            # Get the first Python file as the main script
            main_script = None
            for file_path in test_files:
                if file_path.endswith('.py'):
                    main_script = os.path.basename(file_path)
                    break
            
            if not main_script:
                self.logger.warning("⚠️ No Python script found for test configuration")
                return False
            
            self.logger.info(f"🔧 Updating test configuration with main script: {main_script}")
            
            # Get data plane URI
            load_test_info = self.get_load_test()
            if not load_test_info:
                return False
                
            data_plane_uri = load_test_info.get('properties', {}).get('dataPlaneURI')
            if not data_plane_uri:
                return False
            
            # Update test configuration with main script
            config_url = f"https://{data_plane_uri}/tests/{test_name}?api-version=2024-05-01-preview"
            
            test_config = {
                "testType": "Locust",
                "inputArtifacts": {
                    "testScriptFileInfo": {
                        "fileName": main_script,
                        "fileType": "LOCUST_SCRIPT"
                    }
                }
            }
            
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/merge-patch+json"
            }
            
            response = requests.patch(config_url, headers=headers, json=test_config, timeout=30)
            
            if response.status_code in [200, 201]:
                self.logger.info(f"✅ Test configuration updated with script: {main_script}")
                return True
            else:
                self.logger.error(f"❌ Failed to update test configuration: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error updating test configuration: {e}")
            return False

    def upload_test_files(self, test_files: List[str]) -> bool:
        """
        Upload test files to Azure Load Test resource.
        
        Args:
            test_files: List of absolute file paths to upload
            
        Returns:
            bool: True if all files uploaded successfully
        """
        try:
            if not test_files:
                self.logger.warning("⚠️ No test files provided for upload")
                return True
            
            self.logger.info(f"📁 Uploading {len(test_files)} test files...")
            
            # Get the data plane URI for file uploads
            load_test_info = self.get_load_test()
            if not load_test_info:
                self.logger.error("❌ Load test resource not found for file upload")
                return False
                
            data_plane_uri = load_test_info.get('properties', {}).get('dataPlaneURI')
            if not data_plane_uri:
                self.logger.error("❌ Data plane URI not available for file upload")
                return False
            
            upload_success = True
            for file_path in test_files:
                if self._upload_single_file(file_path, data_plane_uri):
                    self.logger.info(f"   ✅ Uploaded: {file_path}")
                else:
                    self.logger.error(f"   ❌ Failed to upload: {file_path}")
                    upload_success = False
            
            if upload_success:
                self.logger.info("✅ All test files uploaded successfully")
                # Create test configuration with locust type
                self._create_test_configuration()
            else:
                self.logger.error("❌ Some files failed to upload")
                
            return upload_success
            
        except Exception as e:
            self.logger.error(f"❌ Error uploading test files: {e}")
            return False

    def _upload_single_file(self, file_path: str, data_plane_uri: str) -> bool:
        """Upload a single test file to Azure Load Test."""
        try:
            import os
            if not os.path.exists(file_path):
                self.logger.error(f"❌ File not found: {file_path}")
                return False
            
            file_name = os.path.basename(file_path)
            
            # First, create file entry in Azure Load Test
            upload_url = f"https://{data_plane_uri}/tests/{self.load_test_name}/files/{file_name}?api-version=2024-05-01-preview"
            
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Upload file
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream"
            }
            
            response = requests.put(upload_url, headers=headers, data=file_content, timeout=60)
            
            if response.status_code in [200, 201]:
                return True
            else:
                self.logger.error(f"❌ Upload failed for {file_name}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading file {file_path}: {e}")
            return False

    def _create_test_configuration(self) -> bool:
        """Create test configuration with locust engine type."""
        try:
            self.logger.info("🔧 Creating test configuration with Locust engine...")
            
            # Get data plane URI
            load_test_info = self.get_load_test()
            if not load_test_info:
                return False
                
            data_plane_uri = load_test_info.get('properties', {}).get('dataPlaneURI')
            if not data_plane_uri:
                return False
            
            # Create test configuration
            config_url = f"https://{data_plane_uri}/tests/{self.load_test_name}?api-version=2024-05-01-preview"
            
            test_config = {
                "displayName": f"{self.load_test_name} Performance Test",
                "description": "OSDU Performance Test using Locust",
                "engineInstances": 1,
                "loadTestConfiguration": {
                    "engineInstances": 1,
                    "splitCSV": False,
                    "quickStartTest": False
                },
                "testType": "Locust",
                "inputArtifacts": {
                    "testScriptFileInfo": {
                        "fileName": "perf_storage_test.py",  # Default to first file
                        "fileType": "LOCUST_SCRIPT"
                    }
                },
                "environmentVariables": {},
                "secrets": {}
            }
            
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/merge-patch+json"
            }
            
            response = requests.patch(config_url, headers=headers, json=test_config, timeout=30)
            
            if response.status_code in [200, 201]:
                self.logger.info("✅ Test configuration created with Locust engine")
                return True
            else:
                self.logger.error(f"❌ Failed to create test configuration: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error creating test configuration: {e}")
            return False

    def get_app_id_from_load_test_name(self, load_test_name: str) -> str:
        """
        Resolve the application ID from a load test name by finding the associated Object (principal) ID.

        Args:
            load_test_name: Name of the load test instance

        Returns:
            The application ID associated with the load test

        Raises:
            Exception: If the load test name or associated app ID cannot be found
        """
        try:
            # Step 1: Find Object (principal) ID from load test name
            principal_id = self._get_principal_id_from_load_test(load_test_name)
            
            # Step 2: Use Object ID to find the corresponding App ID
            app_id = self._get_app_id_from_principal_id(principal_id)
            
            return app_id
            
        except Exception as e:
            self.logger.error(f"Error resolving app ID for load test '{load_test_name}': {e}")
            raise
    
    def _get_principal_id_from_load_test(self, load_test_name: str) -> str:
        """
        Internal method to get the Object (principal) ID from load test name.
        
        Args:
            load_test_name: Name of the load test instance
            
        Returns:
            The Object (principal) ID
        """
        try:
            # Use Azure Resource Manager API to get load test resource details
            token = self._get_access_token()
            url = (f"{self.management_base_url}/subscriptions/{self.subscription_id}"
                  f"/resourceGroups/{self.resource_group_name}"
                  f"/providers/Microsoft.LoadTestService/loadtests/{load_test_name}"
                  f"?api-version={self.api_version}")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                load_test_data = response.json()
                # Extract principal ID from the managed identity or service principal
                if 'identity' in load_test_data and 'principalId' in load_test_data['identity']:
                    return load_test_data['identity']['principalId']
                else:
                    self.logger.error(f"No principal ID found for load test '{load_test_name}'")
                    raise ValueError(f"No principal ID found for load test '{load_test_name}'")
            else:
                self.logger.error(f"Failed to get load test details: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get load test details: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Error getting principal ID from load test '{load_test_name}': {e}")
            raise
    
    def _get_app_id_from_principal_id(self, principal_id: str) -> str:
        """
        Internal method to get App ID from Object (principal) ID using Microsoft Graph API.
        
        Args:
            principal_id: The Object (principal) ID
            
        Returns:
            The application ID
        """
        try:
            # Use Microsoft Graph API to get service principal details
            token = self._get_access_token(resource="https://graph.microsoft.com/")
            url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{principal_id}"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                service_principal = response.json()
                if 'appId' in service_principal:
                    return service_principal['appId']
                else:
                    self.logger.error(f"No appId found for principal ID '{principal_id}'")
                    raise ValueError(f"No appId found for principal ID '{principal_id}'")
            else:
                self.logger.error(f"Failed to get service principal details: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get service principal details: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Error getting app ID from principal ID '{principal_id}': {e}")
            raise

    def setup_load_test_entitlements(self, load_test_name: str, host: str, partition: str, token: str) -> bool:
        """
        Wrapper function that sets up entitlements for a load test application.
        
        This function:
        1. Resolves the app ID from the load test name
        2. Creates an Entitlement object with OSDU configuration
        3. Creates entitlements for the load test app
        
        Args:
            load_test_name: Name of the load test instance
            host: OSDU host URL (e.g., https://your-osdu-host.com)
            partition: OSDU data partition ID (e.g., opendes)
            token: Bearer token for OSDU authentication
            
        Returns:
            bool: True if entitlements were set up successfully
        """
        try:
            self.logger.info(f"🔧 Setting up entitlements for load test: {load_test_name}")
            
            # Step 1: Get app ID from load test name
            self.logger.info("🔍 Resolving application ID from load test...")
            app_id = self.get_app_id_from_load_test_name(load_test_name)
            self.logger.info(f"✅ Resolved app ID: {app_id}")
            
            # Step 2: Import and create Entitlement object
            from .entitlement import Entitlement
            
            self.logger.info("🔧 Creating entitlement manager...")
            entitlement = Entitlement(
                host=host,
                partition=partition,
                load_test_app_id=app_id,
                token=token
            )
            
            # Step 3: Create entitlements for the load test app
            self.logger.info("🔐 Creating entitlements for load test application...")
            entitlement_result = entitlement.create_entitlment_for_load_test_app()
            
            if entitlement_result['success']:
                self.logger.info(f"✅ Successfully set up entitlements for load test '{load_test_name}'")
                self.logger.info(f"   App ID: {app_id}")
                self.logger.info(f"   Partition: {partition}")
                self.logger.info(f"   Result: {entitlement_result['message']}")
                self.logger.info(f"   Groups processed:")
                
                for group_result in entitlement_result['results']:
                    group_name = group_result['group']
                    if group_result['conflict']:
                        self.logger.info(f"     • {group_name} (already existed)")
                    elif group_result['success']:
                        self.logger.info(f"     • {group_name} (newly added)")
                    else:
                        self.logger.warning(f"     • {group_name} (failed: {group_result['message']})")
                        
                return True
            else:
                self.logger.error(f"❌ Failed to set up entitlements for load test '{load_test_name}'")
                self.logger.error(f"   Result: {entitlement_result['message']}")
                for group_result in entitlement_result['results']:
                    if not group_result['success']:
                        self.logger.error(f"   • {group_result['group']}: {group_result['message']}")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to set up entitlements for load test '{load_test_name}': {e}")
            return False


def main():
    """
    Example usage of the AzureLoadTestManager class.
    """
    # Configuration
    SUBSCRIPTION_ID = "015ab1e4-bd82-4c0d-ada9-0f9e9c68e0c4"
    RESOURCE_GROUP = "janrajcj-rg"
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
        demo_logger.info("🚀 Azure Load Test Manager - SOLID Principles Implementation")
        demo_logger.info("=" * 60)

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
            demo_logger.info(f"✅ Load Testing instance created: {load_test['id']}")
            
            # Get detailed info
            info = runner.get_load_test_info()
            demo_logger.info(f"📊 Load Test Details:")
            demo_logger.info(f"   Name: {info.get('name')}")
            demo_logger.info(f"   Location: {info.get('location')}")
            demo_logger.info(f"   Data Plane URI: {info.get('data_plane_uri')}")
            demo_logger.info(f"   Provisioning State: {info.get('provisioning_state')}")
        
        demo_logger.info("=" * 60)
        demo_logger.info("✅ Azure Load Test Manager execution completed successfully!")
        
    except Exception as e:
        demo_logger.error(f"❌ Error: {e}")
        demo_logger.error("\n🔍 Troubleshooting:")
        demo_logger.error("1. Ensure Azure CLI is installed: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")
        demo_logger.error("2. Login to Azure CLI: az login")
        demo_logger.error("3. Verify subscription: az account show")
        demo_logger.error("4. Check permissions for creating resources")


if __name__ == "__main__":
    main()