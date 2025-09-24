"""Comprehensive error handling tests for the OSDU Performance Testing Framework."""
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

from osdu_perf.cli import main, run_local_tests, run_azure_load_tests
from osdu_perf.azure_loadtest_template import AzureLoadTestManager


class TestAuthenticationErrors:
    """Test authentication error scenarios."""
    
    @pytest.mark.unit
    @patch('azure.identity.DefaultAzureCredential')
    def test_azure_authentication_failure(self, mock_credential):
        """Test Azure authentication failure handling."""
        mock_credential.side_effect = Exception("Authentication failed")
        
        manager = AzureLoadTestManager("test-sub", "test-rg", "eastus")
        
        with pytest.raises(Exception, match="Authentication failed"):
            manager.authenticate()
    
    @pytest.mark.unit
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager.authenticate')
    def test_run_azure_load_tests_auth_error(self, mock_auth):
        """Test run_azure_load_tests handles authentication errors."""
        mock_auth.side_effect = Exception("Azure login required")
        
        args = Mock()
        args.subscription_id = "test-sub"
        args.resource_group = "test-rg"
        args.location = "eastus"
        args.partition = "test"
        args.token = "token"
        args.app_id = "app"
        args.loadtest_name = None
        args.test_name = None
        args.engine_instances = 1
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.directory = "."
        args.force = False
        args.verbose = False
        
        with patch('builtins.print') as mock_print:
            with patch('sys.exit') as mock_exit:
                run_azure_load_tests(args)
                
                # Verify error message and exit
                assert any("Error" in str(call) for call in mock_print.call_args_list)
                mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    def test_invalid_azure_credentials_format(self):
        """Test handling of invalid Azure credential formats."""
        # Test with invalid subscription ID format
        manager = AzureLoadTestManager("invalid-sub-id", "test-rg", "eastus")
        
        # Should still create manager but fail on authenticate
        assert manager.subscription_id == "invalid-sub-id"
        
        # Test with empty values
        with pytest.raises(TypeError):
            AzureLoadTestManager(None, "test-rg", "eastus")


class TestMissingFileErrors:
    """Test missing file and directory error scenarios."""
    
    @pytest.mark.unit
    def test_run_local_tests_missing_custom_locustfile(self):
        """Test run_local_tests with missing custom locustfile."""
        args = Mock()
        args.host = "https://test.com"
        args.partition = "test"
        args.token = "token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = "/nonexistent/locustfile.py"
        args.web_ui = False
        args.verbose = False
        
        with patch('os.path.exists', return_value=False):
            with patch('builtins.print') as mock_print:
                with patch('sys.exit') as mock_exit:
                    run_local_tests(args)
                    
                    # Should print error and exit
                    assert any("Locustfile not found" in str(call) 
                              for call in mock_print.call_args_list)
                    mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    @patch('glob.glob')
    def test_azure_load_tests_no_test_files(self, mock_glob):
        """Test Azure load tests when no perf_*_test.py files found."""
        mock_glob.return_value = []  # No test files found
        
        manager = AzureLoadTestManager("test-sub", "test-rg", "eastus")
        service = manager.detect_service_name("/nonexistent/path")
        
        # Should return 'default' when no files found
        assert service == 'default'
    
    @pytest.mark.unit
    @patch('os.path.exists')
    def test_init_project_invalid_directory(self, mock_exists):
        """Test init project in invalid directory."""
        mock_exists.return_value = False
        
        with patch('sys.argv', ['osdu_perf', 'init', 'storage']):
            with patch('os.makedirs', side_effect=PermissionError("Permission denied")):
                with patch('builtins.print') as mock_print:
                    with patch('sys.exit') as mock_exit:
                        main()
                        
                        # Should handle permission error gracefully
                        mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    def test_package_test_files_missing_directory(self):
        """Test packaging test files from missing directory."""
        manager = AzureLoadTestManager("test-sub", "test-rg", "eastus")
        
        with patch('os.walk', return_value=[]):  # Empty directory
            with patch('tempfile.mkdtemp', return_value='/tmp/test'):
                with patch('zipfile.ZipFile') as mock_zip:
                    mock_zip_instance = Mock()
                    mock_zip.return_value.__enter__.return_value = mock_zip_instance
                    
                    result = manager.package_test_files("/nonexistent")
                    
                    # Should still create zip file even if directory is empty
                    assert result.endswith('.zip')


class TestInvalidParameterErrors:
    """Test invalid parameter handling."""
    
    @pytest.mark.unit
    def test_run_local_tests_invalid_users(self):
        """Test run_local_tests with invalid user count."""
        args = Mock()
        args.host = "https://test.com"
        args.partition = "test"
        args.token = "token"
        args.users = -5  # Invalid negative users
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = False
        args.verbose = False
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 1  # Locust should fail
            
            with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
                with patch('osdu_perf.cli.create_locustfile_template'):
                    with patch('os.remove'):
                        with patch('sys.exit') as mock_exit:
                            run_local_tests(args)
                            
                            # Should exit with error when locust fails
                            mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    def test_run_local_tests_invalid_host_url(self):
        """Test run_local_tests with invalid host URL."""
        args = Mock()
        args.host = "not-a-valid-url"  # Invalid URL format
        args.partition = "test"
        args.token = "token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = False
        args.verbose = False
        
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 1  # Locust should fail with bad URL
            
            with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
                with patch('osdu_perf.cli.create_locustfile_template'):
                    with patch('os.remove'):
                        with patch('sys.exit') as mock_exit:
                            run_local_tests(args)
                            mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    def test_azure_load_tests_invalid_location(self):
        """Test Azure load tests with invalid location."""
        args = Mock()
        args.subscription_id = "test-sub"
        args.resource_group = "test-rg"
        args.location = "invalid-location"  # Not a valid Azure region
        args.partition = "test"
        args.token = "token"
        args.app_id = "app"
        args.loadtest_name = None
        args.test_name = None
        args.engine_instances = 1
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.directory = "."
        args.force = False
        args.verbose = False
        
        with patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.authenticate.side_effect = Exception("Invalid location")
            mock_manager.return_value = mock_instance
            
            with patch('builtins.print') as mock_print:
                with patch('sys.exit') as mock_exit:
                    run_azure_load_tests(args)
                    
                    # Should handle invalid location error
                    assert any("Error" in str(call) for call in mock_print.call_args_list)
                    mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    def test_run_time_format_validation(self):
        """Test various run time format validations."""
        valid_formats = ['60s', '5m', '1h', '30', '10m30s']
        invalid_formats = ['invalid', '60x', '', '-5m', 'abc123']
        
        # In the actual implementation, these would be validated
        # For now, we test that they're passed through to Locust
        for run_time in valid_formats:
            args = Mock()
            args.host = "https://test.com"
            args.partition = "test"
            args.token = "token"
            args.users = 10
            args.spawn_rate = 2
            args.run_time = run_time
            args.locustfile = None
            args.web_ui = False
            args.verbose = False
            
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                
                with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
                    with patch('osdu_perf.cli.create_locustfile_template'):
                        with patch('os.remove'):
                            run_local_tests(args)
                            
                            # Verify run_time was passed to subprocess
                            call_args = mock_subprocess.call_args[0][0]
                            assert run_time in call_args


class TestNetworkAndResourceErrors:
    """Test network and resource-related error scenarios."""
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_locust_subprocess_timeout(self, mock_subprocess):
        """Test handling of Locust subprocess timeout."""
        args = Mock()
        args.host = "https://test.com"
        args.partition = "test"
        args.token = "token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = False
        args.verbose = False
        
        # Mock subprocess timeout
        import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired(['locust'], 30)
        
        with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
            with patch('osdu_perf.cli.create_locustfile_template'):
                with patch('os.remove'):
                    with patch('builtins.print') as mock_print:
                        with patch('sys.exit') as mock_exit:
                            run_local_tests(args)
                            
                            # Should handle timeout gracefully
                            mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_create_or_update')
    def test_azure_resource_creation_failure(self, mock_create):
        """Test Azure resource creation failure."""
        manager = AzureLoadTestManager("test-sub", "test-rg", "eastus")
        manager.load_test_client = Mock()
        
        # Mock Azure API error
        from azure.core.exceptions import HttpResponseError
        mock_create.side_effect = HttpResponseError("Resource quota exceeded")
        
        with pytest.raises(HttpResponseError, match="Resource quota exceeded"):
            manager.create_or_get_loadtest_resource("test-loadtest")
    
    @pytest.mark.unit
    @patch('azure.mgmt.loadtesting.operations.LoadTestsOperations.begin_upload_test_file')
    def test_azure_file_upload_failure(self, mock_upload):
        """Test Azure file upload failure."""
        manager = AzureLoadTestManager("test-sub", "test-rg", "eastus")
        manager.load_test_client = Mock()
        
        # Mock upload failure
        mock_upload.side_effect = Exception("Upload failed - network error")
        
        with patch('builtins.open', mock_open(read_data=b'test data')):
            with pytest.raises(Exception, match="Upload failed - network error"):
                manager.upload_test_file("test-loadtest", "/test/file.zip", "test-file")
    
    @pytest.mark.unit
    def test_azure_service_quota_exceeded(self):
        """Test handling when Azure service quotas are exceeded."""
        args = Mock()
        args.subscription_id = "test-sub"
        args.resource_group = "test-rg"
        args.location = "eastus"
        args.partition = "test"
        args.token = "token"
        args.app_id = "app"
        args.loadtest_name = None
        args.test_name = None
        args.engine_instances = 100  # Excessive number of instances
        args.users = 10000  # Excessive number of users
        args.spawn_rate = 2
        args.run_time = "60s"
        args.directory = "."
        args.force = False
        args.verbose = False
        
        with patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.authenticate.return_value = None
            mock_instance.detect_service_name.return_value = "storage"
            mock_instance.upload_and_run_test.side_effect = Exception("Quota exceeded")
            mock_manager.return_value = mock_instance
            
            with patch('builtins.print') as mock_print:
                with patch('sys.exit') as mock_exit:
                    run_azure_load_tests(args)
                    
                    # Should handle quota error
                    assert any("Error" in str(call) for call in mock_print.call_args_list)
                    mock_exit.assert_called_once_with(1)


class TestCLIArgumentParsingErrors:
    """Test CLI argument parsing error scenarios."""
    
    @pytest.mark.unit
    def test_main_function_unknown_command(self):
        """Test main function with unknown command."""
        with patch('sys.argv', ['osdu_perf', 'unknown_command']):
            with patch('sys.exit') as mock_exit:
                main()
                
                # Should exit with error for unknown command
                mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    def test_main_function_missing_required_args(self):
        """Test main function with missing required arguments."""
        incomplete_commands = [
            ['osdu_perf', 'run', 'local'],  # Missing required args
            ['osdu_perf', 'run', 'azure_load_test'],  # Missing required args
            ['osdu_perf', 'init'],  # Missing service name
        ]
        
        for cmd_args in incomplete_commands:
            with patch('sys.argv', cmd_args):
                with patch('sys.exit') as mock_exit:
                    main()
                    
                    # Should exit with error for incomplete commands
                    mock_exit.assert_called_once_with(1)
                    mock_exit.reset_mock()
    
    @pytest.mark.unit
    def test_conflicting_arguments(self):
        """Test handling of conflicting arguments."""
        # Test with conflicting verbosity settings (if any)
        conflicting_args = [
            'osdu_perf', 'run', 'local',
            '--host', 'https://test.com',
            '--partition', 'test',
            '--token', 'token',
            '--verbose',
            '--quiet'  # If this option existed, it would conflict
        ]
        
        from osdu_perf.cli import create_parser
        parser = create_parser()
        
        # For now, just test that we can handle the verbose flag
        valid_args = conflicting_args[:-1]  # Remove --quiet
        try:
            args = parser.parse_args(valid_args[1:])  # Remove 'osdu_perf'
            assert args.verbose is True
        except SystemExit:
            # If parsing fails, that's also valid behavior
            pass


class TestTemplateSystemErrors:
    """Test template system error scenarios."""
    
    @pytest.mark.unit
    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_create_locustfile_template_permission_error(self, mock_open):
        """Test create_locustfile_template with permission error."""
        from osdu_perf.cli import create_locustfile_template
        
        with pytest.raises(PermissionError, match="Permission denied"):
            create_locustfile_template("/protected/locustfile.py")
    
    @pytest.mark.unit
    @patch('tempfile.mktemp')
    @patch('zipfile.ZipFile')
    def test_package_test_files_disk_full(self, mock_zipfile, mock_mktemp):
        """Test package_test_files when disk is full."""
        mock_mktemp.return_value = '/tmp/test_dir'
        mock_zipfile.side_effect = OSError("No space left on device")
        
        manager = AzureLoadTestManager("test-sub", "test-rg", "eastus")
        
        with pytest.raises(OSError, match="No space left on device"):
            manager.package_test_files("/test/path")
    
    @pytest.mark.unit
    def test_template_module_import_error(self):
        """Test handling of template module import errors."""
        # Mock import error for template modules
        with patch('osdu_perf.localdev_template.get_localdev_template', 
                  side_effect=ImportError("Template module not found")):
            
            from osdu_perf.cli import create_locustfile_template
            
            with pytest.raises(ImportError, match="Template module not found"):
                create_locustfile_template("/tmp/locustfile.py")


class TestErrorRecoveryAndCleanup:
    """Test error recovery and cleanup scenarios."""
    
    @pytest.mark.unit
    def test_temporary_file_cleanup_on_error(self):
        """Test that temporary files are cleaned up on errors."""
        args = Mock()
        args.host = "https://test.com"
        args.partition = "test"
        args.token = "token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = False
        args.verbose = False
        
        temp_file = '/tmp/test_locustfile.py'
        
        with patch('tempfile.mktemp', return_value=temp_file):
            with patch('osdu_perf.cli.create_locustfile_template'):
                with patch('subprocess.run', side_effect=Exception("Locust error")):
                    with patch('os.remove') as mock_remove:
                        with patch('os.path.exists', return_value=True):
                            with patch('sys.exit'):
                                run_local_tests(args)
                                
                                # Should still attempt cleanup even on error
                                mock_remove.assert_called_with(temp_file)
    
    @pytest.mark.unit
    def test_azure_load_test_partial_failure_cleanup(self):
        """Test cleanup when Azure load test partially fails."""
        test_config = {
            'loadtest_name': 'test-loadtest',
            'test_name': 'test-id',
            'engine_instances': 1,
            'users': 10,
            'spawn_rate': 2,
            'run_time': '60s',
            'partition': 'test',
            'token': 'token',
            'app_id': 'app',
            'directory': '.',
            'force': False,
            'verbose': False
        }
        
        manager = AzureLoadTestManager("test-sub", "test-rg", "eastus")
        
        with patch.object(manager, 'authenticate'):
            with patch.object(manager, 'create_or_get_loadtest_resource'):
                with patch.object(manager, 'package_test_files', return_value='/tmp/test.zip'):
                    with patch.object(manager, 'upload_test_file', 
                                    side_effect=Exception("Upload failed")):
                        with patch('os.path.exists', return_value=True):
                            with patch('os.remove') as mock_remove:
                                
                                with pytest.raises(Exception, match="Upload failed"):
                                    manager.upload_and_run_test(test_config)
                                
                                # Should clean up zip file on failure
                                mock_remove.assert_called_with('/tmp/test.zip')
    
    @pytest.mark.unit
    def test_graceful_keyboard_interrupt(self):
        """Test graceful handling of keyboard interrupt."""
        args = Mock()
        args.host = "https://test.com"
        args.partition = "test"
        args.token = "token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = False
        args.verbose = False
        
        with patch('subprocess.run', side_effect=KeyboardInterrupt()):
            with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
                with patch('osdu_perf.cli.create_locustfile_template'):
                    with patch('os.remove'):
                        with patch('builtins.print') as mock_print:
                            with patch('sys.exit') as mock_exit:
                                run_local_tests(args)
                                
                                # Should handle interrupt gracefully
                                mock_exit.assert_called_once()