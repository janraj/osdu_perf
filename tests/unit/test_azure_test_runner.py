"""
Comprehensive unit tests for Azure Test Runner.

Tests Azure Load Testing functionality, resource management, 
and integration with Azure services.
"""

import pytest
import json
import logging
import urllib.error
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from azure.identity import AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.loadtesting import LoadTestMgmtClient
from azure.developer.loadtesting import LoadTestAdministrationClient, LoadTestRunClient

from osdu_perf.operations.azure_test_operation import AzureLoadTestRunner, UrllibResponse


class TestUrllibResponse:
    """Test the UrllibResponse compatibility wrapper."""
    
    def test_urllib_response_initialization(self):
        """Test UrllibResponse initialization with basic parameters."""
        response = UrllibResponse(200, b'{"success": true}')
        
        assert response.status_code == 200
        assert response.content == b'{"success": true}'
        assert response.text == '{"success": true}'
        assert response.headers == {}
    
    def test_urllib_response_with_headers(self):
        """Test UrllibResponse initialization with headers."""
        headers = {"Content-Type": "application/json"}
        response = UrllibResponse(200, b'{"test": "data"}', headers)
        
        assert response.headers == headers
        assert response.status_code == 200
    
    def test_urllib_response_json_parsing(self):
        """Test JSON parsing functionality."""
        json_data = {"message": "success", "code": 200}
        response = UrllibResponse(200, json.dumps(json_data).encode())
        
        parsed_data = response.json()
        assert parsed_data == json_data
    
    def test_urllib_response_empty_content_json(self):
        """Test JSON parsing with empty content."""
        response = UrllibResponse(200, b'')
        
        parsed_data = response.json()
        assert parsed_data == {}
    
    def test_urllib_response_raise_for_status_success(self):
        """Test raise_for_status with successful status codes."""
        response = UrllibResponse(200, b'Success')
        # Should not raise any exception
        response.raise_for_status()
        
        response = UrllibResponse(201, b'Created')
        response.raise_for_status()
    
    def test_urllib_response_raise_for_status_client_error(self):
        """Test raise_for_status with client error status codes."""
        response = UrllibResponse(404, b'Not Found')
        
        with pytest.raises(Exception) as exc_info:
            response.raise_for_status()
        
        assert "HTTP 404" in str(exc_info.value)
    
    def test_urllib_response_raise_for_status_server_error(self):
        """Test raise_for_status with server error status codes."""
        response = UrllibResponse(500, b'Internal Server Error')
        
        with pytest.raises(Exception) as exc_info:
            response.raise_for_status()
        
        assert "HTTP 500" in str(exc_info.value)


class TestAzureLoadTestRunner:
    """Test the main AzureLoadTestRunner class."""
    
    @pytest.fixture
    def mock_credential(self):
        """Mock Azure CLI credential."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential') as mock:
            yield mock.return_value
    
    @pytest.fixture
    def mock_resource_client(self):
        """Mock Azure Resource Management Client."""
        with patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient') as mock:
            yield mock.return_value
    
    @pytest.fixture
    def mock_loadtest_mgmt_client(self):
        """Mock Azure Load Test Management Client."""
        with patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient') as mock:
            yield mock.return_value
    
    @pytest.fixture
    def azure_runner(self, mock_credential, mock_resource_client, mock_loadtest_mgmt_client):
        """Create AzureLoadTestRunner instance with mocked dependencies."""
        return AzureLoadTestRunner(
            subscription_id="test-sub-id",
            resource_group_name="test-rg",
            load_test_name="test-load-test",
            location="eastus",
            tags={"env": "test"}
        )
    
    def test_initialization_default_parameters(self, mock_credential, mock_resource_client, mock_loadtest_mgmt_client):
        """Test AzureLoadTestRunner initialization with default parameters."""
        runner = AzureLoadTestRunner(
            subscription_id="test-sub-id",
            resource_group_name="test-rg", 
            load_test_name="test-load-test"
        )
        
        assert runner.subscription_id == "test-sub-id"
        assert runner.resource_group_name == "test-rg"
        assert runner.load_test_name == "test-load-test"
        assert runner.location == "eastus"
        assert runner.sku == "Standard"
        assert runner.version == "25.1.23"
        assert runner.test_runid_name == "osdu-perf-test"
        assert "Environment" in runner.tags
    
    def test_initialization_custom_parameters(self, mock_credential, mock_resource_client, mock_loadtest_mgmt_client):
        """Test AzureLoadTestRunner initialization with custom parameters."""
        custom_tags = {"project": "osdu", "env": "prod"}
        runner = AzureLoadTestRunner(
            subscription_id="custom-sub-id",
            resource_group_name="custom-rg",
            load_test_name="custom-load-test",
            location="westus",
            tags=custom_tags,
            sku="Premium",
            version="26.0.0",
            test_runid_name="custom-test-run"
        )
        
        assert runner.subscription_id == "custom-sub-id"
        assert runner.location == "westus"
        assert runner.tags == custom_tags
        assert runner.sku == "Premium"
        assert runner.version == "26.0.0"
        assert runner.test_runid_name == "custom-test-run"
    
    def test_logging_setup(self, azure_runner):
        """Test logging configuration is properly set up."""
        assert hasattr(azure_runner, 'logger')
        assert azure_runner.logger.name == "AzureLoadTestRunner"
        assert azure_runner.logger.level == logging.INFO
    
    def test_convert_time_to_seconds_numeric_input(self, azure_runner):
        """Test time conversion with numeric input."""
        assert azure_runner._convert_time_to_seconds("120") == 120
        assert azure_runner._convert_time_to_seconds(60) == 60
    
    def test_convert_time_to_seconds_with_units(self, azure_runner):
        """Test time conversion with time units."""
        # Seconds
        assert azure_runner._convert_time_to_seconds("30s") == 30
        assert azure_runner._convert_time_to_seconds("45") == 45
        
        # Minutes
        assert azure_runner._convert_time_to_seconds("5m") == 300
        assert azure_runner._convert_time_to_seconds("10m") == 600
        
        # Hours
        assert azure_runner._convert_time_to_seconds("1h") == 3600
        assert azure_runner._convert_time_to_seconds("2h") == 7200
    
    def test_convert_time_to_seconds_invalid_input(self, azure_runner):
        """Test time conversion with invalid input."""
        # Invalid format
        assert azure_runner._convert_time_to_seconds("invalid") == 60
        assert azure_runner._convert_time_to_seconds("30x") == 60
        assert azure_runner._convert_time_to_seconds("") == 60
        assert azure_runner._convert_time_to_seconds(None) == 60
    
    def test_convert_time_to_seconds_unknown_unit(self, azure_runner):
        """Test time conversion with unknown time unit."""
        assert azure_runner._convert_time_to_seconds("30d") == 60  # Unknown unit defaults to 60
    
    def test_initialize_credential_success(self, azure_runner):
        """Test successful credential initialization."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential') as mock_cred:
            mock_instance = Mock()
            mock_cred.return_value = mock_instance
            
            credential = azure_runner._initialize_credential()
            
            assert credential == mock_instance
            mock_cred.assert_called_once()
    
    def test_initialize_credential_failure(self, azure_runner):
        """Test credential initialization failure."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential') as mock_cred:
            mock_cred.side_effect = Exception("Auth failed")
            
            with pytest.raises(Exception) as exc_info:
                azure_runner._initialize_credential()
            
            assert "Auth failed" in str(exc_info.value)
    
    def test_init_clients_success(self, azure_runner, mock_credential, mock_resource_client, mock_loadtest_mgmt_client):
        """Test successful Azure SDK clients initialization."""
        azure_runner._init_clients()
        
        assert azure_runner.resource_client == mock_resource_client
        assert azure_runner.loadtest_mgmt_client == mock_loadtest_mgmt_client
        assert azure_runner.loadtest_admin_client is None
        assert azure_runner.loadtest_run_client is None
    
    def test_init_clients_failure(self, azure_runner):
        """Test Azure SDK clients initialization failure."""
        with patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient') as mock_rmc:
            mock_rmc.side_effect = Exception("Client init failed")
            
            with pytest.raises(Exception) as exc_info:
                azure_runner._init_clients()
            
            assert "Client init failed" in str(exc_info.value)
    
    def test_init_data_plane_client_success(self, azure_runner):
        """Test successful data plane client initialization."""
        data_plane_uri = "https://test-loadtest.eastus.test.azure.com"
        principal_id = "test-principal-id"
        
        with patch('osdu_perf.operations.azure_test_runner.LoadTestAdministrationClient') as mock_admin, \
             patch('osdu_perf.operations.azure_test_runner.LoadTestRunClient') as mock_run:
            
            azure_runner._init_data_plane_client(data_plane_uri, principal_id)
            
            assert azure_runner.principal_id == principal_id
            assert azure_runner.data_plane_url == data_plane_uri
            mock_admin.assert_called_once_with(
                endpoint=data_plane_uri,
                credential=azure_runner._credential
            )
            mock_run.assert_called_once_with(
                endpoint=data_plane_uri,
                credential=azure_runner._credential
            )
    
    def test_init_data_plane_client_uri_without_https(self, azure_runner):
        """Test data plane client initialization with URI without https."""
        data_plane_uri = "test-loadtest.eastus.test.azure.com"
        principal_id = "test-principal-id"
        expected_uri = "https://test-loadtest.eastus.test.azure.com"
        
        with patch('osdu_perf.operations.azure_test_runner.LoadTestAdministrationClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestRunClient'):
            
            azure_runner._init_data_plane_client(data_plane_uri, principal_id)
            
            assert azure_runner.data_plane_url == expected_uri
    
    def test_init_data_plane_client_empty_uri(self, azure_runner):
        """Test data plane client initialization with empty URI."""
        with pytest.raises(ValueError) as exc_info:
            azure_runner._init_data_plane_client("", "test-principal-id")
        
        assert "Data plane URI not available" in str(exc_info.value)
    
    def test_init_data_plane_client_failure(self, azure_runner):
        """Test data plane client initialization failure."""
        with patch('osdu_perf.operations.azure_test_runner.LoadTestAdministrationClient') as mock_admin:
            mock_admin.side_effect = Exception("Data plane init failed")
            
            with pytest.raises(Exception) as exc_info:
                azure_runner._init_data_plane_client("https://test.com", "test-id")
            
            assert "Data plane init failed" in str(exc_info.value)


class TestAzureLoadTestRunnerResourceManagement:
    """Test Azure Load Test Runner resource management operations."""
    
    @pytest.fixture
    def azure_runner(self):
        """Create AzureLoadTestRunner instance with mocked dependencies."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential'), \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient') as mock_rmc, \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner = AzureLoadTestRunner(
                subscription_id="test-sub-id",
                resource_group_name="test-rg",
                load_test_name="test-load-test"
            )
            runner.resource_client = mock_rmc.return_value
            return runner
    
    def test_create_resource_group_exists(self, azure_runner):
        """Test create_resource_group when resource group already exists."""
        mock_rg = Mock()
        azure_runner.resource_client.resource_groups.get.return_value = mock_rg
        
        result = azure_runner.create_resource_group()
        
        assert result is True
        azure_runner.resource_client.resource_groups.get.assert_called_once_with("test-rg")
        azure_runner.resource_client.resource_groups.create_or_update.assert_not_called()
    
    def test_create_resource_group_new(self, azure_runner):
        """Test create_resource_group when creating new resource group."""
        # Simulate resource group doesn't exist
        azure_runner.resource_client.resource_groups.get.side_effect = Exception("Not found")
        
        mock_result = Mock()
        azure_runner.resource_client.resource_groups.create_or_update.return_value = mock_result
        
        result = azure_runner.create_resource_group()
        
        assert result is True
        azure_runner.resource_client.resource_groups.create_or_update.assert_called_once()
        
        # Verify the parameters passed to create_or_update
        call_args = azure_runner.resource_client.resource_groups.create_or_update.call_args
        assert call_args[0][0] == "test-rg"  # resource group name
        assert call_args[0][1]['location'] == "eastus"
        assert 'Environment' in call_args[0][1]['tags']
    
    def test_create_resource_group_creation_failure(self, azure_runner):
        """Test create_resource_group when creation fails."""
        azure_runner.resource_client.resource_groups.get.side_effect = Exception("Not found")
        azure_runner.resource_client.resource_groups.create_or_update.side_effect = Exception("Creation failed")
        
        with pytest.raises(Exception) as exc_info:
            azure_runner.create_resource_group()
        
        assert "Creation failed" in str(exc_info.value)


class TestAzureLoadTestRunnerTokenManagement:
    """Test Azure Load Test Runner token management."""
    
    @pytest.fixture
    def azure_runner(self):
        """Create AzureLoadTestRunner instance with mocked dependencies."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential') as mock_cred, \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner = AzureLoadTestRunner(
                subscription_id="test-sub-id",
                resource_group_name="test-rg", 
                load_test_name="test-load-test"
            )
            runner._credential = mock_cred.return_value
            return runner
    
    def test_get_data_plane_token_success(self, azure_runner):
        """Test successful data plane token retrieval."""
        mock_token = Mock()
        mock_token.token = "data-plane-token-123"
        azure_runner._credential.get_token.return_value = mock_token
        
        token = azure_runner.get_data_plane_token()
        
        assert token == "data-plane-token-123"
        azure_runner._credential.get_token.assert_called_once_with("https://cnt-prod.loadtesting.azure.com/.default")
    
    def test_get_data_plane_token_failure(self, azure_runner):
        """Test data plane token retrieval failure."""
        azure_runner._credential.get_token.side_effect = Exception("Token failed")
        
        token = azure_runner.get_data_plane_token()
        
        assert token is None
    
    def test_get_management_token_success(self, azure_runner):
        """Test successful management token retrieval."""
        mock_token = Mock()
        mock_token.token = "management-token-456"
        azure_runner._credential.get_token.return_value = mock_token
        
        token = azure_runner.get_management_token()
        
        assert token == "management-token-456"
        azure_runner._credential.get_token.assert_called_once_with("https://management.azure.com/.default")
    
    def test_get_management_token_failure(self, azure_runner):
        """Test management token retrieval failure."""
        azure_runner._credential.get_token.side_effect = Exception("Token failed")
        
        token = azure_runner.get_management_token()
        
        assert token is None


class TestAzureLoadTestRunnerFileOperations:
    """Test Azure Load Test Runner file upload and management operations."""
    
    @pytest.fixture
    def azure_runner(self):
        """Create AzureLoadTestRunner instance with mocked dependencies."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential'), \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner = AzureLoadTestRunner(
                subscription_id="test-sub-id",
                resource_group_name="test-rg",
                load_test_name="test-load-test"
            )
            runner.data_plane_url = "https://test-loadtest.eastus.test.azure.com"
            return runner
    
    def test_upload_test_files_to_test_success(self, azure_runner):
        """Test successful file upload to test."""
        test_files = ["test1.py", "test2.py"]
        
        # Mock the missing get_load_test method directly on the runner
        mock_load_test_info = {
            'properties': {
                'dataPlaneURI': 'https://test-dataplane.azure.com'
            }
        }
        
        # Add the missing methods to the runner instance
        azure_runner.get_load_test = MagicMock(return_value=mock_load_test_info)
        azure_runner._upload_single_file_to_test = MagicMock(return_value=True)
        azure_runner._update_test_configuration = MagicMock()
        
        result = azure_runner.upload_test_files_to_test("test-name", test_files)
        
        assert result is True
        assert azure_runner._upload_single_file_to_test.call_count == len(test_files)
    
    def test_upload_test_files_to_test_missing_file(self, azure_runner):
        """Test file upload with missing file."""
        test_files = ["missing_file.py"]
        
        with patch('pathlib.Path.exists', return_value=False):
            result = azure_runner.upload_test_files_to_test("test-name", test_files)
            
            assert result is False
    
    def test_upload_test_files_to_test_upload_failure(self, azure_runner):
        """Test file upload with upload failure."""
        test_files = ["test.py"]
        
        with patch.object(azure_runner, 'get_data_plane_token') as mock_token, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.urlopen') as mock_urlopen, \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_token.return_value = "test-token"
            mock_urlopen.side_effect = Exception("Upload failed")
            
            result = azure_runner.upload_test_files_to_test("test-name", test_files)
            
            assert result is False


class TestAzureLoadTestRunnerTestExecution:
    """Test Azure Load Test Runner test execution operations."""
    
    @pytest.fixture
    def azure_runner(self):
        """Create AzureLoadTestRunner instance with mocked dependencies."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential'), \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner = AzureLoadTestRunner(
                subscription_id="test-sub-id",
                resource_group_name="test-rg",
                load_test_name="test-load-test"
            )
            runner.data_plane_url = "https://test-loadtest.eastus.test.azure.com"
            return runner
    
    def test_wait_for_test_validation_success(self, azure_runner):
        """Test successful test validation waiting."""
        with patch.object(azure_runner, 'get_data_plane_token') as mock_token, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.urlopen') as mock_urlopen, \
             patch('time.sleep'):
            
            mock_token.return_value = "test-token"
            
            # Mock successful validation response
            mock_response = Mock()
            mock_response.read.return_value = b'{"validationStatus": "VALIDATION_SUCCESS"}'
            mock_response.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = azure_runner._wait_for_test_validation("test-name")
            
            assert result is True
    
    def test_wait_for_test_validation_failure(self, azure_runner):
        """Test test validation failure."""
        with patch('osdu_perf.operations.azure_test_runner.urllib.request.Request') as mock_request, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.urlopen') as mock_urlopen, \
             patch('time.sleep'):
            
            # Mock validation failure response
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'''{"inputArtifacts": {"testScriptFileInfo": {"fileName": "test.py", "validationStatus": "VALIDATION_FAILURE", "validationFailureDetails": "Test failed"}}}'''
            mock_response.headers = {}
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = azure_runner._wait_for_test_validation("test-name", token="test-token")
            
            assert result is False
    
    def test_wait_for_test_validation_timeout(self, azure_runner):
        """Test test validation timeout."""
        with patch('osdu_perf.operations.azure_test_runner.urllib.request.Request') as mock_request, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.urlopen') as mock_urlopen, \
             patch('time.sleep'), \
             patch('time.time') as mock_time:
            
            # Mock time progression to simulate timeout - provide enough values for all calls
            mock_time.side_effect = [0, 0, 100, 100, 200, 200, 400, 400, 500, 500]  # More values for logging calls
            
            # Mock ongoing validation response
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'''{"inputArtifacts": {"testScriptFileInfo": {"fileName": "test.py", "validationStatus": "VALIDATION_IN_PROGRESS"}}}'''
            mock_response.headers = {}
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = azure_runner._wait_for_test_validation("test-name", max_wait_time=300, token="test-token")
            
            assert result is True  # Method returns True on timeout to allow execution
    
    def test_run_test_success(self, azure_runner):
        """Test successful test run."""
        with patch.object(azure_runner, 'loadtest_run_client') as mock_client:
            
            # Mock successful test run response
            mock_result = {
                "testRunId": "test-run-123",
                "status": "ACCEPTED",
                "displayName": "Test Run"
            }
            mock_client.begin_test_run.return_value = mock_result
            
            result = azure_runner.run_test("test-name", "Test Display Name")
            
            assert result == mock_result
            mock_client.begin_test_run.assert_called_once()
    
    def test_run_test_failure(self, azure_runner):
        """Test test run failure."""
        with patch.object(azure_runner, 'get_data_plane_token') as mock_token, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.urlopen') as mock_urlopen:
            
            mock_token.return_value = "test-token"
            mock_urlopen.side_effect = Exception("Test run failed")
            
            result = azure_runner.run_test("test-name")
            
            assert result is None


class TestAzureLoadTestRunnerEntitlements:
    """Test Azure Load Test Runner entitlement operations."""
    
    @pytest.fixture
    def azure_runner(self):
        """Create AzureLoadTestRunner instance with mocked dependencies."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential'), \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner = AzureLoadTestRunner(
                subscription_id="test-sub-id",
                resource_group_name="test-rg",
                load_test_name="test-load-test"
            )
            runner.principal_id = "test-principal-id"
            return runner
    
    def test_get_app_id_from_principal_id_success(self, azure_runner):
        """Test successful app ID retrieval."""
        with patch.object(azure_runner, '_credential') as mock_credential, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.Request') as mock_request, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.urlopen') as mock_urlopen:
            
            # Mock token
            mock_token = Mock()
            mock_token.token = "test-graph-token"
            mock_credential.get_token.return_value = mock_token
            
            # Mock successful response with app data
            mock_response = Mock()
            app_data = {
                "appId": "test-app-id-123",
                "servicePrincipalType": "Application"
            }
            mock_response.read.return_value = json.dumps(app_data).encode()
            mock_response.status = 200
            mock_response.getcode.return_value = 200
            mock_response.headers = {}  # Provide a real dictionary for headers
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            app_id = azure_runner.get_app_id_from_principal_id("test-principal-id")
            
            assert app_id == "test-app-id-123"
    
    def test_get_app_id_from_principal_id_not_found(self, azure_runner):
        """Test app ID retrieval when no app found."""
        with patch.object(azure_runner, '_credential') as mock_credential, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.Request') as mock_request, \
             patch('osdu_perf.operations.azure_test_runner.urllib.request.urlopen') as mock_urlopen:
            
            # Mock token
            mock_token = Mock()
            mock_token.token = "test-graph-token"
            mock_credential.get_token.return_value = mock_token
            
            # Mock 404 response
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="test-url", 
                code=404, 
                msg="Not Found", 
                hdrs={}, 
                fp=None
            )
            
            with pytest.raises(Exception, match="Failed to get service principal details: 404"):
                azure_runner.get_app_id_from_principal_id("test-principal-id")
    
    def test_get_app_id_from_principal_id_failure(self, azure_runner):
        """Test app ID retrieval failure."""
        with patch.object(azure_runner, '_credential') as mock_credential:
            
            # Mock token failure
            mock_credential.get_token.side_effect = Exception("Token failed")
            
            with pytest.raises(Exception, match="Token failed"):
                azure_runner.get_app_id_from_principal_id("test-principal-id")
    
    def test_setup_load_test_entitlements_success(self, azure_runner):
        """Test successful load test entitlements setup."""
        azure_runner.principal_id = "test-principal-id"
        
        with patch.object(azure_runner, 'get_app_id_from_principal_id') as mock_get_app_id, \
             patch('osdu_perf.operations.entitlement.Entitlement') as mock_entitlement_class:
            
            mock_get_app_id.return_value = "test-app-id"
            mock_entitlement = Mock()
            mock_entitlement.create_entitlment_for_load_test_app.return_value = {
                'success': True,
                'message': 'Entitlements created successfully',
                'results': [
                    {'group': 'test-group', 'success': True, 'conflict': False, 'message': ''}
                ]
            }
            mock_entitlement_class.return_value = mock_entitlement
            
            result = azure_runner.setup_load_test_entitlements(
                "test-load-test",
                "test-host",
                "test-partition",
                "test-token"
            )
            
            assert result is True
    
    def test_setup_load_test_entitlements_no_app_id(self, azure_runner):
        """Test load test entitlements setup when app ID not found."""
        with patch.object(azure_runner, 'get_app_id_from_principal_id') as mock_get_app_id:
            mock_get_app_id.return_value = None
            
            result = azure_runner.setup_load_test_entitlements(
                "test-load-test",
                "test-host",
                "test-partition",
                "test-token"
            )
            
            assert result is False
    
    def test_setup_load_test_entitlements_entitlement_failure(self, azure_runner):
        """Test load test entitlements setup when entitlement creation fails."""
        azure_runner.principal_id = "test-principal-id"
        
        with patch.object(azure_runner, 'get_app_id_from_principal_id') as mock_get_app_id, \
             patch('osdu_perf.operations.entitlement.Entitlement') as mock_entitlement_class:
            
            mock_get_app_id.return_value = "test-app-id"
            mock_entitlement = Mock()
            mock_entitlement.create_entitlment_for_load_test_app.return_value = {
                'success': False,
                'message': 'Entitlements creation failed',
                'results': [
                    {'group': 'test-group', 'success': False, 'conflict': False, 'message': 'Failed to create'}
                ]
            }
            mock_entitlement_class.return_value = mock_entitlement
            
            result = azure_runner.setup_load_test_entitlements(
                "test-load-test",
                "test-host",
                "test-partition",
                "test-token"
            )
            
            assert result is False


class TestAzureLoadTestRunnerEdgeCases:
    """Test edge cases and error scenarios for Azure Load Test Runner."""
    
    def test_initialization_with_empty_subscription_id(self):
        """Test initialization with empty subscription ID."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential'), \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner = AzureLoadTestRunner(
                subscription_id="",
                resource_group_name="test-rg",
                load_test_name="test-load-test"
            )
            
            assert runner.subscription_id == ""
    
    def test_initialization_with_none_tags(self):
        """Test initialization with None tags."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential'), \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner = AzureLoadTestRunner(
                subscription_id="test-sub-id",
                resource_group_name="test-rg",
                load_test_name="test-load-test",
                tags=None
            )
            
            assert "Environment" in runner.tags
            assert "Service" in runner.tags
    
    def test_multiple_initialization_calls(self):
        """Test that multiple initialization calls work correctly."""
        with patch('osdu_perf.operations.azure_test_runner.AzureCliCredential'), \
             patch('osdu_perf.operations.azure_test_runner.ResourceManagementClient'), \
             patch('osdu_perf.operations.azure_test_runner.LoadTestMgmtClient'):
            
            runner1 = AzureLoadTestRunner(
                subscription_id="test-sub-id-1",
                resource_group_name="test-rg-1",
                load_test_name="test-load-test-1"
            )
            
            runner2 = AzureLoadTestRunner(
                subscription_id="test-sub-id-2",
                resource_group_name="test-rg-2",
                load_test_name="test-load-test-2"
            )
            
            assert runner1.subscription_id != runner2.subscription_id
            assert runner1.resource_group_name != runner2.resource_group_name
            assert runner1.load_test_name != runner2.load_test_name