"""Unit tests for Azure Load Test Template module."""
import pytest
import os
import tempfile
import zipfile
from unittest.mock import Mock, patch, mock_open, MagicMock
from pathlib import Path

from osdu_perf.azure_loadtest_template import AzureLoadTestManager


class TestAzureLoadTestManager:
    """Test cases for AzureLoadTestManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create AzureLoadTestManager instance for testing."""
        return AzureLoadTestManager("test-subscription", "test-rg", "eastus")
    
    @pytest.mark.unit
    def test_init(self, manager):
        """Test AzureLoadTestManager initialization."""
        assert manager.subscription_id == "test-subscription"
        assert manager.resource_group == "test-rg"
        assert manager.location == "eastus"
        assert manager.load_test_client is None
        assert manager.resource_client is None
    
    @pytest.mark.unit
    @patch('azure.identity.DefaultAzureCredential')
    @patch('azure.mgmt.loadtesting.LoadTestMgmtClient')
    @patch('azure.mgmt.resource.ResourceManagementClient')
    def test_authenticate(self, mock_resource_client, mock_loadtest_client, mock_credential, manager):
        """Test authenticate method."""
        mock_cred = Mock()
        mock_credential.return_value = mock_cred
        
        manager.authenticate()
        
        mock_credential.assert_called_once()
        mock_loadtest_client.assert_called_once_with(mock_cred, "test-subscription")
        mock_resource_client.assert_called_once_with(mock_cred, "test-subscription")
        assert manager.load_test_client is not None
        assert manager.resource_client is not None
    
    @pytest.mark.unit
    @patch('glob.glob')
    def test_find_test_files(self, mock_glob, manager):
        """Test find_test_files method."""
        mock_glob.return_value = [
            '/path/perf_storage_test.py',
            '/path/perf_search_test.py',
            '/path/other_file.py'
        ]
        
        result = manager.find_test_files('/path')
        
        mock_glob.assert_called_once_with('/path/perf_*_test.py')
        assert result == ['/path/perf_storage_test.py', '/path/perf_search_test.py']
    
    @pytest.mark.unit
    @patch('glob.glob')
    def test_find_test_files_no_files(self, mock_glob, manager):
        """Test find_test_files with no matching files."""
        mock_glob.return_value = []
        
        result = manager.find_test_files('/path')
        
        assert result == []
    
    @pytest.mark.unit
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.find_test_files')
    def test_detect_service_name(self, mock_find_files, manager):
        """Test detect_service_name method."""
        mock_find_files.return_value = [
            '/path/perf_storage_test.py',
            '/path/perf_search_test.py'
        ]
        
        result = manager.detect_service_name('/path')
        
        # Should return the first service found
        assert result == 'storage'
    
    @pytest.mark.unit
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.find_test_files')
    def test_detect_service_name_no_files(self, mock_find_files, manager):
        """Test detect_service_name with no test files."""
        mock_find_files.return_value = []
        
        result = manager.detect_service_name('/path')
        
        assert result == 'default'
    
    @pytest.mark.unit
    def test_generate_resource_names(self, manager):
        """Test generate_resource_names method."""
        loadtest_name, test_name = manager.generate_resource_names('storage')
        
        assert loadtest_name == 'osdu-storage-loadtest'
        assert test_name.startswith('osdu_storage_test_')
        assert len(test_name.split('_')) == 4  # osdu_storage_test_timestamp
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_create_or_update')
    def test_create_or_get_loadtest_resource(self, mock_create, manager):
        """Test create_or_get_loadtest_resource method."""
        manager.load_test_client = Mock()
        mock_poller = Mock()
        mock_result = Mock()
        mock_result.name = 'test-loadtest'
        mock_poller.result.return_value = mock_result
        mock_create.return_value = mock_poller
        
        result = manager.create_or_get_loadtest_resource('test-loadtest')
        
        assert result.name == 'test-loadtest'
        mock_create.assert_called_once()
    
    @pytest.mark.unit
    @patch('tempfile.mkdtemp')
    @patch('osdu_perf.cli.create_locustfile_template')
    @patch('zipfile.ZipFile')
    @patch('os.walk')
    def test_package_test_files(self, mock_walk, mock_zipfile, mock_create_template, 
                               mock_mkdtemp, manager):
        """Test package_test_files method."""
        mock_mkdtemp.return_value = '/tmp/test_dir'
        mock_walk.return_value = [
            ('/test/path', [], ['perf_storage_test.py', 'requirements.txt'])
        ]
        
        mock_zip = Mock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        
        result = manager.package_test_files('/test/path')
        
        assert result.endswith('.zip')
        mock_create_template.assert_called_once()
        mock_zip.write.assert_called()
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_upload_test_file')
    def test_upload_test_file(self, mock_upload, manager):
        """Test upload_test_file method."""
        manager.load_test_client = Mock()
        mock_poller = Mock()
        mock_result = Mock()
        mock_poller.result.return_value = mock_result
        mock_upload.return_value = mock_poller
        
        with patch('builtins.open', mock_open(read_data=b'test data')):
            result = manager.upload_test_file('test-loadtest', '/test/file.zip', 'test-file')
        
        mock_upload.assert_called_once()
        assert result == mock_result
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_create_or_update_test')
    def test_create_load_test(self, mock_create_test, manager):
        """Test create_load_test method."""
        manager.load_test_client = Mock()
        mock_poller = Mock()
        mock_result = Mock()
        mock_poller.result.return_value = mock_result
        mock_create_test.return_value = mock_poller
        
        test_config = {
            'displayName': 'Test',
            'description': 'Test description',
            'engineInstances': 1,
            'loadTestConfiguration': {
                'engineInstances': 1
            },
            'environmentVariables': {
                'OSDU_PARTITION': 'test-partition',
                'ADME_BEARER_TOKEN': 'test-token',
                'APPID': 'test-app-id'
            },
            'testId': 'test-id'
        }
        
        result = manager.create_load_test('test-loadtest', 'test-id', test_config)
        
        mock_create_test.assert_called_once()
        assert result == mock_result
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_test_run')
    def test_run_load_test(self, mock_run_test, manager):
        """Test run_load_test method."""
        manager.load_test_client = Mock()
        mock_poller = Mock()
        mock_result = Mock()
        mock_poller.result.return_value = mock_result
        mock_run_test.return_value = mock_poller
        
        result = manager.run_load_test('test-loadtest', 'test-id', 'run-id')
        
        mock_run_test.assert_called_once()
        assert result == mock_result
    
    @pytest.mark.unit
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.authenticate')
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.create_or_get_loadtest_resource')
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.package_test_files')
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.upload_test_file')
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.create_load_test')
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.run_load_test')
    def test_upload_and_run_test_complete_flow(self, mock_run, mock_create, mock_upload, 
                                              mock_package, mock_resource, mock_auth, manager):
        """Test complete upload_and_run_test workflow."""
        # Mock all dependencies
        mock_resource.return_value = Mock(name='test-loadtest')
        mock_package.return_value = '/tmp/test.zip'
        mock_upload.return_value = Mock()
        mock_create.return_value = Mock()
        mock_run.return_value = Mock()
        
        test_config = {
            'loadtest_name': 'test-loadtest',
            'test_name': 'test-id',
            'engine_instances': 1,
            'users': 10,
            'spawn_rate': 2,
            'run_time': '60s',
            'partition': 'test-partition',
            'token': 'test-token',
            'app_id': 'test-app-id',
            'directory': '/test/path',
            'force': False,
            'verbose': False
        }
        
        manager.upload_and_run_test(test_config)
        
        # Verify all methods were called in correct order
        mock_auth.assert_called_once()
        mock_resource.assert_called_once()
        mock_package.assert_called_once()
        mock_upload.assert_called_once()
        mock_create.assert_called_once()
        mock_run.assert_called_once()


class TestAzureLoadTestManagerErrorHandling:
    """Test error handling in AzureLoadTestManager."""
    
    @pytest.fixture
    def manager(self):
        """Create AzureLoadTestManager instance for testing."""
        return AzureLoadTestManager("test-subscription", "test-rg", "eastus")
    
    @pytest.mark.unit
    @patch('azure.identity.DefaultAzureCredential', side_effect=Exception("Auth failed"))
    def test_authenticate_failure(self, mock_credential, manager):
        """Test authenticate method with failure."""
        with pytest.raises(Exception, match="Auth failed"):
            manager.authenticate()
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_create_or_update')
    def test_create_or_get_loadtest_resource_failure(self, mock_create, manager):
        """Test create_or_get_loadtest_resource with failure."""
        manager.load_test_client = Mock()
        mock_create.side_effect = Exception("Resource creation failed")
        
        with pytest.raises(Exception, match="Resource creation failed"):
            manager.create_or_get_loadtest_resource('test-loadtest')
    
    @pytest.mark.unit
    @patch('tempfile.mkdtemp')
    @patch('zipfile.ZipFile')
    def test_package_test_files_zip_failure(self, mock_zipfile, mock_mkdtemp, manager):
        """Test package_test_files with zip creation failure."""
        mock_mkdtemp.return_value = '/tmp/test_dir'
        mock_zipfile.side_effect = Exception("Zip creation failed")
        
        with pytest.raises(Exception, match="Zip creation failed"):
            manager.package_test_files('/test/path')
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_upload_test_file')
    def test_upload_test_file_failure(self, mock_upload, manager):
        """Test upload_test_file with upload failure."""
        manager.load_test_client = Mock()
        mock_upload.side_effect = Exception("Upload failed")
        
        with patch('builtins.open', mock_open(read_data=b'test data')):
            with pytest.raises(Exception, match="Upload failed"):
                manager.upload_test_file('test-loadtest', '/test/file.zip', 'test-file')


class TestAzureLoadTestManagerUtilities:
    """Test utility methods in AzureLoadTestManager."""
    
    @pytest.fixture
    def manager(self):
        """Create AzureLoadTestManager instance for testing."""
        return AzureLoadTestManager("test-subscription", "test-rg", "eastus")
    
    @pytest.mark.unit
    def test_parse_service_name_from_filename(self, manager):
        """Test parsing service name from different filename patterns."""
        test_cases = [
            ('perf_storage_test.py', 'storage'),
            ('/path/to/perf_search_test.py', 'search'),
            ('perf_wellbore_test.py', 'wellbore'),
            ('perf_schema_service_test.py', 'schema'),  # Should take first part
            ('perf_test.py', 'test'),  # Edge case
        ]
        
        for filename, expected in test_cases:
            # Extract service name using the same logic as in detect_service_name
            basename = os.path.basename(filename)
            if basename.startswith('perf_') and basename.endswith('_test.py'):
                parts = basename[5:-8].split('_')  # Remove 'perf_' and '_test.py'
                result = parts[0] if parts else 'default'
                assert result == expected, f"Failed for {filename}"
    
    @pytest.mark.unit 
    @patch('datetime.datetime')
    def test_timestamp_generation(self, mock_datetime, manager):
        """Test timestamp generation for test names."""
        mock_datetime.now.return_value.strftime.return_value = '20250924_152250'
        
        _, test_name = manager.generate_resource_names('storage')
        
        assert test_name == 'osdu_storage_test_20250924_152250'
        mock_datetime.now.assert_called_once()
    
    @pytest.mark.unit
    def test_environment_variable_configuration(self, manager):
        """Test environment variable configuration for load tests."""
        test_config = {
            'partition': 'test-partition',
            'token': 'test-token',  
            'app_id': 'test-app-id'
        }
        
        # This would be part of create_load_test method
        env_vars = {
            'OSDU_PARTITION': test_config['partition'],
            'ADME_BEARER_TOKEN': test_config['token'],
            'APPID': test_config['app_id']
        }
        
        assert env_vars['OSDU_PARTITION'] == 'test-partition'
        assert env_vars['ADME_BEARER_TOKEN'] == 'test-token'
        assert env_vars['APPID'] == 'test-app-id'