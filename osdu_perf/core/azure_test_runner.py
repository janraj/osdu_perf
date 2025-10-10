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
        self._credential = AzureCliCredential()
        
        # Initialize Azure SDK clients
        self._init_clients()
        
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
    
    
    def _init_clients(self) -> None:
        """Initialize Azure SDK clients."""
        try:
            # Resource Management Client for resource group operations
            self.resource_client = ResourceManagementClient(
                credential=self._credential,
                subscription_id=self.subscription_id
            )
            
            # Load Test Management Client for resource operations
            self.loadtest_mgmt_client = LoadTestMgmtClient(
                credential=self._credential,
                subscription_id=self.subscription_id
            )
            
            # Load Testing Clients will be initialized after resource creation
            self.loadtest_admin_client = None
            self.loadtest_run_client = None

            self.logger.info(f"Azure SDK clients initialized successfully {self.subscription_id}")

        except Exception as e:
            self.logger.error(f"Failed to initialize Azure SDK clients: {e}")
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
            else:
                raise ValueError("Data plane URI not available")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize data plane client using SDK: {e}")
            raise

    
    def create_resource_group(self) -> bool:
        """
        Create the resource group if it doesn't exist.
        
        Returns:
            bool: True if resource group exists or was created successfully
        """
        try:
            print(f"Checking if resource group '{self.resource_group_name}' exists...")
            
            # Check if resource group exists
            try:
                rg = self.resource_client.resource_groups.get(self.resource_group_name)
                print(f"Resource group '{self.resource_group_name}' already exists")
                return True
            except Exception as e:
                # Resource group doesn't exist, create it
                print(f"Creating resource group '{self.resource_group_name}'...  and error is {e}")

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
            self.logger.error(f"Error creating resource group: {e}")
            raise
    

    
    def create_load_test_resource(self) -> Optional[Dict[str, Any]]:
        """
        Create the Azure Load Test resource using REST API.
        
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

        except Exception:
            # Resource doesn't exist, create it
            self.logger.info(f"Creating new load test resource...")

            try:
                create_operation = self.loadtest_mgmt_client.load_tests.begin_create_or_update(
                    resource_group_name=self.resource_group_name,
                    load_test_name=self.load_test_name,
                    load_test_resource=load_test_data
                )
                
                # Wait for creation to complete
                resource = create_operation.result()
                self.logger.info(f"Load test resource '{self.load_test_name}' created successfully")
                self.logger.info(f"  Resource ID: {resource.id}")
                self.logger.info(f"  Data Plane URI: {resource.data_plane_uri} identity.principal_id={resource.identity.principal_id}")
            except Exception as e:
                self.logger.error(f"Failed to create load test resource: {e}")
                raise
        
        # Initialize data plane client
        self._init_data_plane_client(resource.data_plane_uri, resource.identity.principal_id)

        return resource.as_dict()

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
        self.logger.info(f"Uploading {len(test_files)} files using data plane url = {data_plane_url} to test name {test_name}")
        
        try:
            for file_path in test_files:
                if not file_path.exists():
                    self.logger.warning(f"File does not exist: {file_path} dataplane url {data_plane_url}")
                    continue

                self.logger.info(f"Uploading file: {file_path.name}")

                # Determine file type - Locust scripts should use JMX_FILE type
                # JMX_FILE: Main test scripts locustfile.py
                # ADDITIONAL_ARTIFACTS: Supporting files (requirements.txt, utilities, perf.*test.py)
                if file_path.name.lower() == 'locustfile.py':
                    file_type = "JMX_FILE"  # Main Locust configuration file
                else:
                    file_type = "ADDITIONAL_ARTIFACTS"  # All other files (requirements.txt, perf_.*_test.py)
                
                # Upload file
                with open(file_path, 'rb') as file_content:
                    result = self.loadtest_admin_client.begin_upload_test_file(
                        test_id=test_name,
                        file_name=file_path.name,
                        file_type=file_type,
                        body=file_content
                    ).result()  # Wait for upload to complete
                
                uploaded_files.append({
                    'fileName': file_path.name,
                    'fileType': file_type,
                    'result': result
                })
                '''
                # Upload file using direct data plane API working code commenting out for now
                url = f"{data_plane_url}/tests/{test_name}/files/{file_path.name}?api-version={self.api_version}&fileType={file_type}"
                
                headers = {
                    "Authorization": f"Bearer {data_plane_token}",
                    "Content-Type": "application/octet-stream"
                }
                
                # Read and upload file content
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                # Create urllib request for file upload
                req = urllib.request.Request(url, data=file_content, method='PUT')
                
                # Add headers
                for key, value in headers.items():
                    req.add_header(key, value)
                
                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        response_obj = UrllibResponse(response.getcode(), response.read(), dict(response.headers))
                except urllib.error.HTTPError as e:
                    error_content = e.read() if hasattr(e, 'read') else b''
                    response_obj = UrllibResponse(e.code, error_content, dict(e.headers) if hasattr(e, 'headers') else {})
                
                response = response_obj
                
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
                '''
                self.logger.info(f"Successfully uploaded: {file_path.name} as {file_type}")
                
        except Exception as e:
            self.logger.error(f"Error uploading files: {e}")

        return uploaded_files

    def create_tests_and_upload_test_files(self, test_name: str, test_directory: str = '.', 
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
            self.logger.info(f"Searching for test files in: {test_directory}")
            
            # Search patterns for performance test files and locustfile
            search_patterns = [
                os.path.join(test_directory, "perf_*_test.py"),
                os.path.join(test_directory, "**", "perf_*_test.py"),
                os.path.join(test_directory, "perf_*test.py"),
                os.path.join(test_directory, "**", "perf_*test.py"),
                os.path.join(test_directory, "locustfile.py"),
                os.path.join(test_directory, "requirements.txt")
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

            self.logger.info(f"Found {len(test_files)} performance test files:")
            for test_file in test_files:
                rel_path = os.path.relpath(test_file, test_directory)
                self.logger.info(f"   • {rel_path}")
            self.logger.info("")
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
            data_plane_token = self.get_data_plane_token()
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
                engine_instances=engine_instances
            )
            if not test_result:
                self.logger.error("Failed to create test in Azure Load Test resource")
                return False
            else:
                self.logger.info(f"Test '{test_name}' created successfully")
                # Step 2: Upload test files using data plane API
                self.logger.info(f"Calling _upload_files_for_test_dataplane. {len(test_files)} test files uploading using Data Plane API...")
                uploaded_files = self._upload_files_for_test_dataplane(test_name, path_objects, self.data_plane_url, data_plane_token)
                if uploaded_files:
                    self.logger.info(f"Successfully uploaded {len(uploaded_files)} files")
                else:
                    self.logger.warning(f"No files were uploaded.")

            self.logger.info(f"Test '{test_name}' created and files uploaded successfully!")

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

    def _wait_for_test_validation(self, test_name: str, max_wait_time: int = 300, token: str = None) -> bool:
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
            data_plane_url = self.data_plane_url
            data_plane_token = token  # self._get_data_plane_token()
            
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
                    # Create urllib request for test status check
                    req = urllib.request.Request(test_status_url)
                    
                    # Add headers
                    for key, value in headers.items():
                        req.add_header(key, value)
                    
                    try:
                        with urllib.request.urlopen(req, timeout=30) as response:
                            response_obj = UrllibResponse(response.getcode(), response.read(), dict(response.headers))
                    except urllib.error.HTTPError as e:
                        error_content = e.read() if hasattr(e, 'read') else b''
                        response_obj = UrllibResponse(e.code, error_content, dict(e.headers) if hasattr(e, 'headers') else {})
                    
                    response = response_obj
                    
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
            token: Azure Data Plane API token
        Returns:
            Dict[str, Any]: The test execution data, or None if failed
        """
        try:
            if not self.loadtest_run_client:
                raise ValueError("Data plane client not initialized. Create load test resource first.")

            self.logger.info(f"Starting test run for test '{test_name}' and run name '{display_name}'...")
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

            # Prepare test run configuration
            test_run_config = {
                'testId': test_name,
                'displayName': display_name,
                'description': f"Load test run created by osdu_perf framework"
            }
            
            # Start the test run
            result = self.loadtest_run_client.begin_test_run(
                test_run_id=f"{test_name}-run-1",
                body=test_run_config
            ).result()  # Wait for test run to start

            self.logger.info(f"✅ Test run '{test_name}' started successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error running test '{test_name}': {e}")
        return None

        '''
        try:
            
            self.logger.info(f"Starting test execution for '{test_name}' using Data Plane API...")
            token = self.get_data_plane_token()
            # Wait for test script validation to complete before starting execution
            if not self._wait_for_test_validation(test_name, token):
                self.logger.error(f"Test script validation failed for '{test_name}'")
                return None
            
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
            execution_url = f"{self.data_plane_url}/test-runs/{test_name}-run-{timestamp}?api-version={self.api_version}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/merge-patch+json"
            }
            
            # Build the test run configuration
            test_run_config = {
                "testId": test_name,
                "displayName": execution_config["displayName"],
                "description": f"Load test execution for {test_name} via OSDU Performance Framework"
            }
            
            # Create urllib request for test execution
            json_payload = json.dumps(test_run_config).encode('utf-8')
            req = urllib.request.Request(execution_url, data=json_payload, method='PATCH')
            
            # Add headers
            for key, value in headers.items():
                req.add_header(key, value)
            
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    response_obj = UrllibResponse(response.getcode(), response.read(), dict(response.headers))
            except urllib.error.HTTPError as e:
                error_content = e.read() if hasattr(e, 'read') else b''
                response_obj = UrllibResponse(e.code, error_content, dict(e.headers) if hasattr(e, 'headers') else {})
            
            response = response_obj
            
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
                        
                        # Create urllib request for retry
                        retry_req = urllib.request.Request(execution_url, data=json_payload, method='PATCH')
                        
                        # Add headers
                        for key, value in headers.items():
                            retry_req.add_header(key, value)
                        
                        try:
                            with urllib.request.urlopen(retry_req, timeout=30) as retry_response:
                                retry_response_obj = UrllibResponse(retry_response.getcode(), retry_response.read(), dict(retry_response.headers))
                        except urllib.error.HTTPError as e:
                            error_content = e.read() if hasattr(e, 'read') else b''
                            retry_response_obj = UrllibResponse(e.code, error_content, dict(e.headers) if hasattr(e, 'headers') else {})
                        
                        retry_response = retry_response_obj
                        
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
        '''

       
    def get_app_id_from_principal_id(self, principal_id: str) -> str:
        """
        Internal method to get App ID from Object (principal) ID using Microsoft Graph API.
        
        Args:
            principal_id: The Object (principal) ID
            
        Returns:
            The application ID
        """
        try:
            # Use Microsoft Graph API to get service principal details
            self.logger.info(f"Acquiring token for graph")
            token = self._credential.get_token("https://graph.microsoft.com/")
            token = token.token
            url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{principal_id}"
            
            # Create urllib request for service principal lookup
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    response_obj = UrllibResponse(response.getcode(), response.read(), dict(response.headers))
            except urllib.error.HTTPError as e:
                error_content = e.read() if hasattr(e, 'read') else b''
                response_obj = UrllibResponse(e.code, error_content, dict(e.headers) if hasattr(e, 'headers') else {})
            
            response = response_obj
            
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

    def setup_load_test_entitlements(self, load_test_name: str, host: str, partition: str, osdu_adme_token: str) -> bool:
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
            self.logger.info(f"Setting up entitlements for load test: {load_test_name}")
            
            # Step 1: Get app ID from load test name
            self.logger.info("Resolving application ID from load test...")
            app_id = self.get_app_id_from_principal_id(self.principal_id)
            self.logger.info(f"Resolved app ID: {app_id}")
            
            # Step 2: Import and create Entitlement object
            from .entitlement import Entitlement
            
            self.logger.info("Creating entitlement manager...")
            entitlement = Entitlement(
                host=host,
                partition=partition,
                load_test_app_id=app_id,
                token=osdu_adme_token
            )
            
            # Step 3: Create entitlements for the load test app
            self.logger.info("Creating entitlements for load test application...")
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
        demo_logger.info("Azure Load Test Manager")
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
        load_test = runner.create_load_test_resource()
        
        if load_test:
            demo_logger.info(f"[main] Load Testing instance created: {load_test['id']}")
            
        
        demo_logger.info("=" * 60)
        demo_logger.info("[main] Azure Load Test Manager execution completed successfully!")
        
    except Exception as e:
        demo_logger.error(f"[main] Error: {e}")
        demo_logger.error("\n[main] Troubleshooting:")
        demo_logger.error("1. Ensure Azure CLI is installed: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli")
        demo_logger.error("2. Login to Azure CLI: az login")
        demo_logger.error("3. Verify subscription: az account show")
        demo_logger.error("4. Check permissions for creating resources")

    runner.create_tests_and_upload_test_files("demo_test", test_directory="./perf_tests", host="https://your-osdu-host.com", partition="opendes", app_id="your-app-id")

if __name__ == "__main__":
    main()