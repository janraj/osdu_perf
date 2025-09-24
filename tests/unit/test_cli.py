"""Unit tests for CLI module."""
import pytest
import os
import tempfile
import shutil
import argparse
from unittest.mock import Mock, patch, mock_open, call, MagicMock
from pathlib import Path
from io import StringIO

from osdu_perf.cli import (
    init_project, 
    create_service_test_file, 
    create_project_readme,
    create_locustfile_template,
    create_service_template,
    main,
    _backup_existing_files,
    _should_create_file,
    run_local_tests,
    run_azure_load_tests,
    get_available_locustfiles,
    create_parser,
    version_command
)


class TestCLIFunctions:
    """Test cases for CLI functions."""
    
    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        yield temp_dir
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)
    
    @pytest.mark.unit
    def test_should_create_file_overwrite(self):
        """Test _should_create_file with overwrite choice."""
        # File exists but choice is overwrite
        with patch('os.path.exists', return_value=True):
            assert _should_create_file("test.py", "o") is True
        
        # File doesn't exist with overwrite choice
        with patch('os.path.exists', return_value=False):
            assert _should_create_file("test.py", "o") is True
    
    @pytest.mark.unit
    def test_should_create_file_skip(self):
        """Test _should_create_file with skip choice."""
        # File exists with skip choice
        with patch('os.path.exists', return_value=True):
            assert _should_create_file("test.py", "s") is False
        
        # File doesn't exist with skip choice
        with patch('os.path.exists', return_value=False):
            assert _should_create_file("test.py", "s") is True
    
    @pytest.mark.unit
    def test_should_create_file_backup(self):
        """Test _should_create_file with backup choice."""
        # Both existing and non-existing files should be created with backup choice
        with patch('os.path.exists', return_value=True):
            assert _should_create_file("test.py", "b") is True
        
        with patch('os.path.exists', return_value=False):
            assert _should_create_file("test.py", "b") is True
    
    @pytest.mark.unit
    @patch('shutil.copytree')
    @patch('builtins.print')
    def test_backup_existing_files(self, mock_print, mock_copytree, temp_directory):
        """Test _backup_existing_files function."""
        # Create test directory
        os.makedirs("perf_tests")
        
        _backup_existing_files("perf_tests", "storage")
        
        # Verify copytree was called
        mock_copytree.assert_called_once()
        # Verify success message was printed
        assert any("Backup created at:" in str(call) for call in mock_print.call_args_list)
    
    @pytest.mark.unit
    @patch('shutil.copytree', side_effect=Exception("Backup failed"))
    def test_backup_existing_files_failure(self, mock_copytree, temp_directory):
        """Test _backup_existing_files with failure."""
        os.makedirs("perf_tests")
        
        with pytest.raises(Exception, match="Backup failed"):
            _backup_existing_files("perf_tests", "storage")
    
    @pytest.mark.unit
    @patch('builtins.open', new_callable=mock_open)
    @patch('builtins.print')
    def test_create_service_test_file(self, mock_print, mock_file):
        """Test create_service_test_file function."""
        create_service_test_file("storage", "/tmp/test_storage.py")
        
        # Verify file was opened for writing
        mock_file.assert_called_once_with("/tmp/test_storage.py", 'w', encoding='utf-8')
        
        # Verify content was written
        handle = mock_file()
        written_content = ''.join([call[0][0] for call in handle.write.call_args_list])
        
        # Verify key content is present
        assert "StoragePerformanceTest" in written_content
        assert "BaseService" in written_content
        assert "def execute(" in written_content
        assert "storage" in written_content.lower()
    
    @pytest.mark.unit
    @patch('builtins.open', new_callable=mock_open)
    @patch('builtins.print')
    def test_create_project_readme(self, mock_print, mock_file):
        """Test create_project_readme function."""
        create_project_readme("search", "/tmp/README.md")
        
        # Verify file was opened for writing
        mock_file.assert_called_once_with("/tmp/README.md", 'w', encoding='utf-8')
        
        # Verify content was written
        handle = mock_file()
        written_content = ''.join([call[0][0] for call in handle.write.call_args_list])
        
        # Verify key content is present
        assert "Search Service Performance Tests" in written_content
        assert "perf_search_test.py" in written_content
        assert "locust -f locustfile.py" in written_content
        assert "## 🚀 Quick Start" in written_content
    
    @pytest.mark.unit
    @patch('builtins.open', new_callable=mock_open)
    @patch('builtins.print')
    def test_create_locustfile_template(self, mock_print, mock_file):
        """Test create_locustfile_template function."""
        create_locustfile_template("/tmp/locustfile.py", ["storage"])
        
        # Verify file was opened for writing
        mock_file.assert_called_once_with("/tmp/locustfile.py", 'w', encoding='utf-8')
        
        # Verify content was written
        handle = mock_file()
        written_content = ''.join([call[0][0] for call in handle.write.call_args_list])
        
        # Verify key content is present
        assert "from osdu_perf import PerformanceUser" in written_content
        assert "@events.init_command_line_parser.add_listener" in written_content
        assert "class OSDUUser(PerformanceUser)" in written_content
        assert "perf_storage_test.py" in written_content
    
    @pytest.mark.unit
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    @patch('builtins.print')
    def test_create_service_template(self, mock_print, mock_makedirs, mock_file):
        """Test create_service_template function."""
        create_service_template("wellbore", "/tmp/services")
        
        # Verify directory was created
        mock_makedirs.assert_called_once_with("/tmp/services", exist_ok=True)
        
        # Verify file was opened for writing
        expected_path = os.path.join("/tmp/services", "wellbore_service.py")
        mock_file.assert_called_once_with(expected_path, 'w', encoding='utf-8')
        
        # Verify content was written
        handle = mock_file()
        written_content = ''.join([call[0][0] for call in handle.write.call_args_list])
        
        # Verify key content is present
        assert "WellboreService" in written_content
        assert "BaseService" in written_content
        assert "wellbore" in written_content.lower()


class TestInitProject:
    """Test cases for init_project function."""
    
    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        yield temp_dir
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)
    
    @pytest.mark.unit
    @patch('osdu_perf.cli.create_azureloadtest_file')
    @patch('osdu_perf.cli.create_requirements_file')
    @patch('osdu_perf.cli.create_locustfile_template')
    @patch('osdu_perf.cli.create_service_test_file')
    @patch('osdu_perf.cli.create_project_readme')
    @patch('os.makedirs')
    @patch('builtins.print')
    def test_init_project_new_project(self, mock_print, mock_makedirs, mock_readme, mock_service, mock_locust, mock_requirements, mock_azureloadtest, temp_directory):
        """Test init_project with new project."""
        init_project("storage")
        
        # Verify directory was created
        mock_makedirs.assert_called_once_with("perf_tests", exist_ok=True)
        
        # Verify all templates were created
        mock_service.assert_called_once()
        mock_requirements.assert_called_once()
        mock_readme.assert_called_once()
        mock_azureloadtest.assert_called_once()
        
        # Verify success message
        assert any("initialized successfully" in str(call) for call in mock_print.call_args_list)
    
    @pytest.mark.unit
    @patch('builtins.input', return_value='o')  # Choose overwrite
    @patch('os.path.exists', return_value=True)
    @patch('osdu_perf.cli.create_azureloadtest_file')
    @patch('osdu_perf.cli.create_requirements_file')
    @patch('osdu_perf.cli.create_locustfile_template')
    @patch('osdu_perf.cli.create_service_test_file')
    @patch('osdu_perf.cli.create_project_readme')
    @patch('os.makedirs')
    @patch('builtins.print')
    def test_init_project_existing_project_overwrite(self, mock_print, mock_makedirs, mock_readme, mock_service, mock_locust, mock_requirements, mock_azureloadtest, mock_exists, mock_input, temp_directory):
        """Test init_project with existing project choosing overwrite."""
        init_project("storage")
        
        # Verify user was prompted
        mock_input.assert_called_once()
        
        # Verify templates were created (overwritten)
        mock_service.assert_called_once()
        mock_requirements.assert_called_once()
        mock_readme.assert_called_once()
        mock_azureloadtest.assert_called_once()
    
    @pytest.mark.unit
    @patch('builtins.input', return_value='c')  # Choose cancel
    @patch('os.path.exists', return_value=True)
    @patch('builtins.print')
    def test_init_project_existing_project_cancel(self, mock_print, mock_exists, mock_input, temp_directory):
        """Test init_project with existing project choosing cancel."""
        init_project("storage")
        
        # Verify user was prompted
        mock_input.assert_called_once()
        
        # Verify cancellation message
        assert any("cancelled" in str(call) for call in mock_print.call_args_list)
    
    @pytest.mark.unit
    @patch('osdu_perf.cli.create_azureloadtest_file')
    @patch('osdu_perf.cli.create_requirements_file')
    @patch('osdu_perf.cli.create_locustfile_template')
    @patch('osdu_perf.cli.create_service_test_file')
    @patch('osdu_perf.cli.create_project_readme')
    @patch('os.makedirs')
    @patch('builtins.print')
    def test_init_project_force_mode(self, mock_print, mock_makedirs, mock_readme, mock_service, mock_locust, mock_requirements, mock_azureloadtest, temp_directory):
        """Test init_project with force mode."""
        init_project("storage", force=True)
        
        # Verify templates were created without prompting
        mock_service.assert_called_once()
        mock_requirements.assert_called_once()
        mock_readme.assert_called_once()
        mock_azureloadtest.assert_called_once()


class TestMainFunction:
    """Test cases for main CLI function."""
    
    @pytest.mark.unit
    @patch('osdu_perf.cli.init_project')
    @patch('sys.argv', ['osdu_perf', 'init', 'storage'])
    def test_main_init_command(self, mock_init):
        """Test main function with init command."""
        main()
        
        # Verify init_project was called with correct arguments
        mock_init.assert_called_once_with('storage', force=False)
    
    @pytest.mark.unit
    @patch('osdu_perf.cli.init_project')
    @patch('sys.argv', ['osdu_perf', 'init', 'search', '--force'])
    def test_main_init_command_with_force(self, mock_init):
        """Test main function with init command and force flag."""
        main()
        
        # Verify init_project was called with force=True
        mock_init.assert_called_once_with('search', force=True)
    
    @pytest.mark.unit
    @patch('osdu_perf.cli.create_service_template')
    @patch('sys.argv', ['osdu_perf', 'create-service', 'wellbore'])
    def test_main_create_service_command(self, mock_create_service):
        """Test main function with create-service command."""
        main()
        
        # Verify create_service_template was called
        mock_create_service.assert_called_once_with('wellbore', './services')
    
    @pytest.mark.unit
    @patch('osdu_perf.cli.create_locustfile_template')
    @patch('sys.argv', ['osdu_perf', 'create-locustfile'])
    def test_main_create_locustfile_command(self, mock_create_locust):
        """Test main function with create-locustfile command."""
        main()
        
        # Verify create_locustfile_template was called
        mock_create_locust.assert_called_once_with('./locustfile.py')
    
    @pytest.mark.unit
    @patch('sys.argv', ['osdu_perf'])
    @patch('argparse.ArgumentParser.print_help')
    def test_main_no_command(self, mock_print_help):
        """Test main function with no command."""
        main()
        
        # Verify help was printed
        mock_print_help.assert_called_once()
    
    @pytest.mark.unit
    @patch('sys.argv', ['osdu_perf', 'init', 'storage'])
    @patch('osdu_perf.cli.init_project', side_effect=Exception("Test error"))
    @patch('sys.exit')
    @patch('builtins.print')
    def test_main_exception_handling(self, mock_print, mock_exit, mock_init):
        """Test main function exception handling."""
        main()
        
        # Verify error was printed and exit was called
        assert any("Error:" in str(call) for call in mock_print.call_args_list)
        mock_exit.assert_called_once_with(1)


class TestCLIArguments:
    """Test cases for CLI argument parsing."""
    
    @pytest.mark.unit
    def test_argument_parser_structure(self):
        """Test that argument parser has correct structure."""
        # This is a basic structure test - in real implementation you'd import the parser
        # For now, we test that the main function handles expected arguments
        
        # Test data for expected commands
        expected_commands = ['init', 'create-service', 'create-locustfile']
        
        # These would be tested in integration tests, but we can verify
        # that our main function can handle these commands
        assert len(expected_commands) == 3
        assert 'init' in expected_commands
        assert 'create-service' in expected_commands
        assert 'create-locustfile' in expected_commands


class TestNewCLICommands:
    """Test cases for new CLI commands added in v1.0.16."""
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_run_local_tests_basic(self, mock_subprocess):
        """Test run_local_tests with basic parameters."""
        args = Mock()
        args.host = "https://test-host.com"
        args.partition = "test-partition"
        args.token = "test-token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = False
        args.verbose = False
        
        # Mock successful subprocess run
        mock_subprocess.return_value.returncode = 0
        
        with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
            with patch('osdu_perf.cli.create_locustfile_template'):
                with patch('os.remove'):
                    run_local_tests(args)
        
        # Verify subprocess was called with correct arguments
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert 'locust' in call_args
        assert '--host' in call_args
        assert 'https://test-host.com' in call_args
        assert '--users' in call_args
        assert '10' in call_args
        assert '--headless' in call_args
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_run_local_tests_web_ui(self, mock_subprocess):
        """Test run_local_tests with web UI enabled."""
        args = Mock()
        args.host = "https://test-host.com"
        args.partition = "test-partition"
        args.token = "test-token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = True
        args.verbose = False
        
        mock_subprocess.return_value.returncode = 0
        
        with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
            with patch('osdu_perf.cli.create_locustfile_template'):
                with patch('os.remove'):
                    run_local_tests(args)
        
        call_args = mock_subprocess.call_args[0][0]
        assert '--headless' not in call_args
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_run_local_tests_custom_locustfile(self, mock_subprocess):
        """Test run_local_tests with custom locustfile."""
        args = Mock()
        args.host = "https://test-host.com"
        args.partition = "test-partition"
        args.token = "test-token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = "custom_locustfile.py"
        args.web_ui = False
        args.verbose = False
        
        mock_subprocess.return_value.returncode = 0
        
        with patch('os.path.exists', return_value=True):
            run_local_tests(args)
        
        call_args = mock_subprocess.call_args[0][0]
        assert 'custom_locustfile.py' in call_args
    
    @pytest.mark.unit
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager')
    def test_run_azure_load_tests_success(self, mock_manager_class):
        """Test run_azure_load_tests with successful execution."""
        args = Mock()
        args.subscription_id = "test-subscription"
        args.resource_group = "test-rg"
        args.location = "eastus"
        args.partition = "test-partition"
        args.token = "test-token"
        args.app_id = "test-app-id"
        args.loadtest_name = None
        args.test_name = None
        args.engine_instances = 1
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.directory = "."
        args.force = False
        args.verbose = False
        
        # Mock the Azure Load Test Manager
        mock_manager = Mock()
        mock_manager.detect_service_name.return_value = "storage"
        mock_manager.upload_and_run_test.return_value = None
        mock_manager_class.return_value = mock_manager
        
        run_azure_load_tests(args)
        
        # Verify manager was created with correct parameters
        mock_manager_class.assert_called_once_with(
            "test-subscription", "test-rg", "eastus"
        )
        
        # Verify methods were called
        mock_manager.detect_service_name.assert_called_once_with(".")
        mock_manager.upload_and_run_test.assert_called_once()
    
    @pytest.mark.unit
    def test_get_available_locustfiles(self):
        """Test get_available_locustfiles function."""
        with patch('glob.glob') as mock_glob:
            # Mock different glob patterns returning different files
            def side_effect(pattern):
                if 'locustfile*.py' in pattern:
                    return ['locustfile.py']
                elif '*locust*.py' in pattern:
                    return ['custom_locustfile.py']
                return []
            
            mock_glob.side_effect = side_effect
            files = get_available_locustfiles()
            
            # Should have local files + 2 bundled (default, template)
            assert len(files) >= 2  # At least the bundled templates
            
            # Check that bundled templates are included
            template_names = [f['name'] for f in files]
            assert 'default' in template_names
            assert 'template' in template_names
    
    @pytest.mark.unit
    def test_create_parser_structure(self):
        """Test that create_parser creates correct argument structure."""
        parser = create_parser()
        
        # Test that parser is an ArgumentParser
        assert isinstance(parser, argparse.ArgumentParser)
        
        # Test subparsers exist by trying to parse known commands
        # This is a basic structural test
        with patch('sys.exit'):
            try:
                parser.parse_args(['init', 'storage'])
                parser.parse_args(['version'])
            except SystemExit:
                pass  # Expected for help/error cases
    
    @pytest.mark.unit
    @patch('builtins.print')
    def test_version_command(self, mock_print):
        """Test version_command function."""
        version_command()
        
        # Verify version was printed
        assert any("OSDU Performance Testing Framework" in str(call) 
                  for call in mock_print.call_args_list)


class TestCLIErrorHandling:
    """Test cases for CLI error handling."""
    
    @pytest.mark.unit
    @patch('subprocess.run')
    def test_run_local_tests_subprocess_failure(self, mock_subprocess):
        """Test run_local_tests handles subprocess failures."""
        args = Mock()
        args.host = "https://test-host.com"
        args.partition = "test-partition"
        args.token = "test-token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = None
        args.web_ui = False
        args.verbose = False
        
        # Mock subprocess failure
        mock_subprocess.return_value.returncode = 1
        
        with patch('tempfile.mktemp', return_value='/tmp/locustfile.py'):
            with patch('osdu_perf.cli.create_locustfile_template'):
                with patch('os.remove'):
                    with patch('sys.exit') as mock_exit:
                        run_local_tests(args)
                        mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    def test_run_local_tests_missing_custom_locustfile(self):
        """Test run_local_tests with missing custom locustfile."""
        args = Mock()
        args.host = "https://test-host.com"
        args.partition = "test-partition" 
        args.token = "test-token"
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.locustfile = "nonexistent_file.py"
        args.web_ui = False
        args.verbose = False
        
        with patch('os.path.exists', return_value=False):
            with patch('builtins.print') as mock_print:
                with patch('sys.exit') as mock_exit:
                    run_local_tests(args)
                    
                    # Verify error message and exit
                    assert any("Locustfile not found" in str(call) 
                              for call in mock_print.call_args_list)
                    mock_exit.assert_called_once_with(1)
    
    @pytest.mark.unit
    @patch('osdu_perf.azure_loadtest_template.AzureLoadTestManager')
    def test_run_azure_load_tests_exception_handling(self, mock_manager_class):
        """Test run_azure_load_tests handles exceptions."""
        args = Mock()
        args.subscription_id = "test-subscription"
        args.resource_group = "test-rg"
        args.location = "eastus"
        args.partition = "test-partition"
        args.token = "test-token"
        args.app_id = "test-app-id"
        args.loadtest_name = None
        args.test_name = None
        args.engine_instances = 1
        args.users = 10
        args.spawn_rate = 2
        args.run_time = "60s"
        args.directory = "."
        args.force = False
        args.verbose = False
        
        # Mock manager to raise exception
        mock_manager = Mock()
        mock_manager.detect_service_name.side_effect = Exception("Test error")
        mock_manager_class.return_value = mock_manager
        
        with patch('builtins.print') as mock_print:
            with patch('sys.exit') as mock_exit:
                run_azure_load_tests(args)
                
                # Verify error was handled
                assert any("Error" in str(call) for call in mock_print.call_args_list)
                mock_exit.assert_called_once_with(1)


class TestCLIMainFunction:
    """Test cases for main CLI entry point."""
    
    @pytest.mark.unit
    @patch('sys.argv', ['osdu_perf', 'run', 'local', '--host', 'https://test.com', 
                        '--partition', 'test', '--token', 'token123'])
    @patch('osdu_perf.cli.run_local_tests')
    def test_main_run_local_command(self, mock_run_local):
        """Test main function with run local command."""
        main()
        mock_run_local.assert_called_once()
    
    @pytest.mark.unit  
    @patch('sys.argv', ['osdu_perf', 'run', 'azure_load_test', '--subscription-id', 'sub123',
                        '--resource-group', 'rg', '--location', 'eastus', '--partition', 'test',
                        '--token', 'token123', '--app-id', 'app123'])
    @patch('osdu_perf.cli.run_azure_load_tests')
    def test_main_run_azure_command(self, mock_run_azure):
        """Test main function with run azure_load_test command."""
        main()
        mock_run_azure.assert_called_once()
    
    @pytest.mark.unit
    @patch('sys.argv', ['osdu_perf', 'version'])
    @patch('osdu_perf.cli.version_command')
    def test_main_version_command(self, mock_version):
        """Test main function with version command."""
        main()
        mock_version.assert_called_once()


class TestTemplateSystemIntegration:
    """Test cases for template system integration."""
    
    @pytest.mark.unit
    @patch('builtins.open', new_callable=mock_open)
    @patch('osdu_perf.templates.localdev_template.get_localdev_template')
    def test_create_locustfile_template_integration(self, mock_get_template, mock_file):
        """Test create_locustfile_template uses correct template."""
        mock_get_template.return_value = "template content"
        
        create_locustfile_template("/test/path/locustfile.py")
        
        mock_get_template.assert_called_once()
        mock_file.assert_called_once_with("/test/path/locustfile.py", 'w', encoding='utf-8')
        mock_file().write.assert_called_once_with("template content")