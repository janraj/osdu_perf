"""
Test cases for CLI command classes.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from osdu_perf.cli.commands.version_command import VersionCommand
from osdu_perf.cli.commands.init_command import InitCommand
from osdu_perf.cli.commands.run_local_command import LocalTestCommand
from osdu_perf.cli.commands.run_azure_command import AzureLoadTestCommand
from osdu_perf.cli.command_registry import CommandRegistry


class TestVersionCommand:
    """Test cases for VersionCommand."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.logger_mock = Mock()
        self.version_command = VersionCommand(self.logger_mock)
    
    def test_validate_args_always_returns_true(self):
        """Test that validate_args always returns True for version command."""
        args = Mock()
        result = self.version_command.validate_args(args)
        assert result is True
    
    def test_execute_success(self):
        """Test successful execution of version command."""
        args = Mock()
        with patch.object(self.version_command, 'version_command') as mock_version:
            result = self.version_command.execute(args)
            mock_version.assert_called_once()
            assert result == 0
    
    def test_execute_handles_exception(self):
        """Test that execute handles exceptions properly."""
        args = Mock()
        with patch.object(self.version_command, 'version_command', side_effect=Exception("test error")):
            with patch.object(self.version_command, 'handle_error', return_value=1) as mock_handle:
                result = self.version_command.execute(args)
                mock_handle.assert_called_once()
                assert result == 1
    
    def test_version_command_basic_info(self):
        """Test version_command displays basic information."""
        self.version_command.version_command()
        
        # Check that logger.info was called multiple times
        assert self.logger_mock.info.call_count >= 3
        
        # Check that version and location info are logged
        calls = [call.args[0] for call in self.logger_mock.info.call_args_list]
        version_calls = [call for call in calls if "OSDU Performance Testing Framework" in call]
        location_calls = [call for call in calls if "Location:" in call]
        deps_calls = [call for call in calls if "Dependencies:" in call]
        
        assert len(version_calls) >= 1
        assert len(location_calls) >= 1
        assert len(deps_calls) >= 1
    
    def test_version_command_basic_dependency_info(self):
        """Test version_command displays dependency information."""
        self.version_command.version_command()
        
        # Check that logger.info was called multiple times
        assert self.logger_mock.info.call_count >= 3
        
        # Check that version and location info are logged
        calls = [call.args[0] for call in self.logger_mock.info.call_args_list]
        version_calls = [call for call in calls if "OSDU Performance Testing Framework" in call]
        location_calls = [call for call in calls if "Location:" in call]
        deps_calls = [call for call in calls if "Dependencies:" in call]
        
        assert len(version_calls) >= 1
        assert len(location_calls) >= 1
        assert len(deps_calls) >= 1


class TestInitCommand:
    """Test cases for InitCommand."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.logger_mock = Mock()
        self.init_command = InitCommand(self.logger_mock)
    
    def test_validate_args_success(self):
        """Test successful args validation."""
        args = Mock()
        args.service_name = "test_service"
        
        result = self.init_command.validate_args(args)
        assert result is True
    
    def test_validate_args_missing_service_name(self):
        """Test validation failure when service_name is missing."""
        args = Mock()
        args.service_name = None
        
        result = self.init_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_empty_service_name(self):
        """Test validation failure when service_name is empty."""
        args = Mock()
        args.service_name = ""
        
        result = self.init_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_no_service_name_attribute(self):
        """Test validation failure when args has no service_name attribute."""
        args = Mock(spec=[])  # Mock with no attributes
        
        result = self.init_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_execute_validation_failure(self):
        """Test execute when validation fails."""
        args = Mock()
        args.service_name = None
        
        result = self.init_command.execute(args)
        assert result == 1


class TestCommandRegistry:
    """Test cases for CommandRegistry."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.logger_mock = Mock()
        self.registry = CommandRegistry(self.logger_mock)
    
    def test_build_parser_returns_parser(self):
        """Test build_parser returns an ArgumentParser."""
        parser = self.registry.build_parser()
        assert parser is not None

    def test_registered_commands_include_all(self):
        """Test that all expected commands are auto-registered."""
        from osdu_perf.cli.command_base import Command
        names = [cls.name for cls in Command._registry]
        assert 'init' in names
        assert 'version' in names
        assert 'local' in names
        assert 'azure_load_test' in names

    def test_resolve_init_command(self):
        """Test resolving the init command."""
        parser = self.registry.build_parser()
        args = parser.parse_args(['init', 'storage'])
        cmd = self.registry.resolve(args)
        assert isinstance(cmd, InitCommand)

    def test_resolve_version_command(self):
        """Test resolving the version command."""
        parser = self.registry.build_parser()
        args = parser.parse_args(['version'])
        cmd = self.registry.resolve(args)
        assert isinstance(cmd, VersionCommand)

    def test_resolve_local_command(self):
        """Test resolving the local command."""
        parser = self.registry.build_parser()
        args = parser.parse_args(['run', 'local', '--scenario', 's', '--token', 't'])
        cmd = self.registry.resolve(args)
        assert isinstance(cmd, LocalTestCommand)

    def test_resolve_azure_command(self):
        """Test resolving the azure_load_test command."""
        parser = self.registry.build_parser()
        args = parser.parse_args(['run', 'azure_load_test', '--scenario', 's', '--token', 't'])
        cmd = self.registry.resolve(args)
        assert isinstance(cmd, AzureLoadTestCommand)

    def test_resolve_and_execute_version(self):
        """Test resolving and executing the version command."""
        parser = self.registry.build_parser()
        args = parser.parse_args(['version'])
        cmd = self.registry.resolve(args)
        with patch.object(cmd, 'version_command'):
            result = cmd.execute(args)
            assert result == 0

    def test_invalid_command_raises_system_exit(self):
        """Test that invalid commands raise SystemExit."""
        parser = self.registry.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(['unknown_command'])
            
            # Check that invocation was logged
            calls = [call.args[0] for call in self.logger_mock.info.call_args_list]
            invocation_calls = [call for call in calls if "Command Invoker is called with command: version" in call]
            execution_calls = [call for call in calls if "Executing command: version" in call]
            
            assert len(invocation_calls) >= 1
            assert len(execution_calls) >= 1