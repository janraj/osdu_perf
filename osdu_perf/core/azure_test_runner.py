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

    def _get_access_token(self) -> str:
        """Get Azure management API access token."""
        try:
            token = self._credential.get_token("https://management.azure.com/.default")
            return token.token
        except Exception as e:
            self.logger.error(f"❌ Failed to get access token: {e}")
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

    def create_test(self, test_name: str, test_files: List[Path]) -> Optional[Dict[str, Any]]:
        """
        Create a test using Azure Load Testing Data Plane API (like working samplejan.py).
        
        Args:
            test_name: Name of the test to create
            test_files: List of test files to upload with the test
            
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
            
            # Locust test configuration (following samplejan.py structure)
            # Ensure displayName is within 2-50 character limit
            display_name = f"OSDU-{test_name}"
            if len(display_name) > 50:
                display_name = f"OSDU-{test_name[:40]}"  # Keep within 50 char limit
            
            body = {
                "displayName": display_name,
                "description": "Load test for OSDU performance using Locust framework",
                "kind": "Locust",  # Specify Locust as the testing framework
                "loadTestConfiguration": {
                    "engineInstances": 2,
                    "splitAllCSVs": False,
                    "quickStartTest": False
                },
                "passFailCriteria": {
                    "passFailMetrics": {}
                },
                "environmentVariables": {},
                "secrets": {}
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
                file_type = "JMX_FILE" if file_path.name.endswith('.py') and 'perf' in file_path.name.lower() else "ADDITIONAL_ARTIFACTS"
                
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

    def setup_test_files(self, test_name: str, test_directory: str = '.') -> bool:
        """
        Complete test files setup: find, copy, and upload test files to Azure Load Test resource.
        
        Args:
            test_name: Name of the test for directory creation
            test_directory: Directory to search for test files
            
        Returns:
            bool: True if setup completed successfully
        """
        import os
        import shutil
        import glob
        
        try:
            print(f"🔍 Searching for perf_*_test.py files in: {test_directory}")
            
            # Search patterns for performance test files
            search_patterns = [
                os.path.join(test_directory, "perf_*_test.py"),
                os.path.join(test_directory, "**", "perf_*_test.py"),
                os.path.join(test_directory, "perf_*test.py"),
                os.path.join(test_directory, "**", "perf_*test.py")
            ]
            
            test_files = []
            for pattern in search_patterns:
                found_files = glob.glob(pattern, recursive=True)
                test_files.extend(found_files)
            
            # Remove duplicates and sort
            test_files = sorted(list(set(test_files)))
            
            if not test_files:
                print("❌ No perf_*_test.py files found!")
                print("   Make sure you have performance test files following the naming pattern:")
                print("   - perf_storage_test.py")
                print("   - perf_search_test.py") 
                print("   - etc.")
                return False
            
            print(f"✅ Found {len(test_files)} performance test files:")
            for test_file in test_files:
                rel_path = os.path.relpath(test_file, test_directory)
                print(f"   • {rel_path}")
            print("")
            
            # Create output directory for processed test files
            output_dir = os.path.join(test_directory, f"azure_load_test_{test_name}")
            os.makedirs(output_dir, exist_ok=True)
            
            print(f"📁 Creating test package in: {output_dir}")
            
            # Copy test files to output directory
            copied_files = []
            for test_file in test_files:
                filename = os.path.basename(test_file)
                dest_path = os.path.join(output_dir, filename)
                
                try:
                    shutil.copy2(test_file, dest_path)
                    copied_files.append(dest_path)
                    print(f"   ✅ Copied: {filename}")
                except Exception as e:
                    print(f"   ❌ Failed to copy {filename}: {e}")
            
            if not copied_files:
                print("❌ No test files were successfully copied!")
                return False
            
            # Convert file paths to Path objects for the new workflow
            path_objects = [Path(f) for f in copied_files]
            
            # Create the test with files using the new Azure Load Testing workflow
            print("")
            print(f"🧪 Creating test '{test_name}' with files using Azure Load Testing workflow...")
            test_result = self.create_test(test_name, path_objects)
            if not test_result:
                print("❌ Failed to create test in Azure Load Test resource")
                return False
            
            print(f"✅ Test '{test_name}' created and files uploaded successfully!")
            print("🔧 Test is ready with Locust engine type")
            
            print("")
            print(f"📊 Test Resource: {self.load_test_name}")
            print(f"🧪 Test Name: {test_name}")
            print(f"🌐 Resource Group: {self.resource_group_name}")
            print(f"📍 Location: {self.location}")
            print(f"📁 Test Files Directory: {output_dir}")
            print(f"📝 Test Files: {len(copied_files)} files")
            print(f"🧪 Test Type: Locust")
            print("")
            print("💡 Next Steps:")
            print("   1. Review the test configuration in Azure Portal")
            print("   2. Configure test parameters (users, duration, etc.)")
            print("   3. Run the load test through Azure Portal or Azure CLI")
            print("")
            print("🔗 Azure Load Testing Portal:")
            print(f"   https://portal.azure.com/#@{self.subscription_id}/resource/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group_name}/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error setting up test files: {e}")
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

    def run_test(self, test_name: str, display_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Start a test execution using Azure Load Testing REST API.
        
        Args:
            test_name: Name of the test to run
            display_name: Display name for the test run (optional)
            
        Returns:
            Dict[str, Any]: The test execution data, or None if failed
        """
        try:
            self.logger.info(f"🚀 Starting test execution for '{test_name}'...")
            
            # Create execution configuration
            execution_config = {
                "displayName": display_name or f"{test_name}-run-{int(time.time())}"
            }
            
            # Start test execution using Management API
            execution_url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group_name}/providers/Microsoft.LoadTestService/loadtests/{self.load_test_name}/tests/{test_name}/executions?api-version=2022-12-01"
            
            headers = {
                "Authorization": f"Bearer {self._get_token()}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(execution_url, headers=headers, json=execution_config, timeout=30)
            
            if response.status_code in [200, 201]:
                result = response.json() if response.content else {}
                execution_id = result.get('name', 'unknown')
                self.logger.info(f"✅ Test execution started successfully - Execution ID: {execution_id}")
                return result
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