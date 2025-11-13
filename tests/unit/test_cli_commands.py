"""
Test cases for CLI command classes.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from osdu_perf.cli.commands.version_command import VersionCommand
from osdu_perf.cli.commands.init_command import InitCommand
from osdu_perf.cli.command_factory import CommandFactory
from osdu_perf.cli.command_invoker import CommandInvoker


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
    
    @patch('osdu_perf.operations.init_runner.InitRunner')
    def test_execute_success(self, mock_init_runner_class):
        """Test successful execution of init command."""
        args = Mock()
        args.service_name = "test_service"
        args.force = False
        
        mock_init_runner = Mock()
        mock_init_runner_class.return_value = mock_init_runner
        
        result = self.init_command.execute(args)
        
        mock_init_runner_class.assert_called_once()
        mock_init_runner.init_project.assert_called_once_with("test_service", False)
        assert result == 0
    
    def test_execute_validation_failure(self):
        """Test execute when validation fails."""
        args = Mock()
        args.service_name = None
        
        result = self.init_command.execute(args)
        assert result == 1
    
    @patch('osdu_perf.operations.init_runner.InitRunner')
    def test_execute_handles_exception(self, mock_init_runner_class):
        """Test that execute handles exceptions properly."""
        args = Mock()
        args.service_name = "test_service"
        args.force = False
        
        mock_init_runner_class.side_effect = Exception("test error")
        
        with patch.object(self.init_command, 'handle_error', return_value=1) as mock_handle:
            result = self.init_command.execute(args)
            mock_handle.assert_called_once()
            assert result == 1


class TestCommandFactory:
    """Test cases for CommandFactory."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.logger_mock = Mock()
        self.factory = CommandFactory(self.logger_mock)
    
    def test_initialization(self):
        """Test CommandFactory initialization."""
        assert hasattr(self.factory, 'logger')
        assert hasattr(self.factory, '_commands')
        assert 'init' in self.factory._commands
        assert 'local' in self.factory._commands
        assert 'azure_load_test' in self.factory._commands
        assert 'version' in self.factory._commands
        
        # Check that initialization log was called
        self.logger_mock.info.assert_called()
    
    def test_create_command_init(self):
        """Test creating init command."""
        command = self.factory.create_command('init')
        
        assert command is not None
        assert isinstance(command, InitCommand)
        assert command.logger == self.logger_mock
    
    def test_create_command_version(self):
        """Test creating version command."""
        command = self.factory.create_command('version')
        
        assert command is not None
        assert isinstance(command, VersionCommand)
        assert command.logger == self.logger_mock
    
    def test_create_command_unknown(self):
        """Test creating unknown command returns None."""
        command = self.factory.create_command('unknown_command')
        
        assert command is None
        self.logger_mock.error.assert_called_with("Unknown command class for: unknown_command")
    
    def test_create_command_logs_creation(self):
        """Test that command creation is logged."""
        self.factory.create_command('version')
        
        # Check that creation was logged
        calls = [call.args[0] for call in self.logger_mock.info.call_args_list]
        creation_calls = [call for call in calls if "Creating command: version" in call]
        assert len(creation_calls) >= 1
    
    def test_get_available_commands(self):
        """Test getting available commands."""
        commands = self.factory.get_available_commands()
        
        assert isinstance(commands, list)
        assert 'init' in commands
        assert 'local' in commands
        assert 'azure_load_test' in commands
        assert 'version' in commands


class TestCommandInvoker:
    """Test cases for CommandInvoker."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.logger_mock = Mock()
        self.invoker = CommandInvoker(self.logger_mock)
    
    def test_initialization(self):
        """Test CommandInvoker initialization."""
        assert self.invoker.logger == self.logger_mock
        assert hasattr(self.invoker, 'factory')
        assert isinstance(self.invoker.factory, CommandFactory)
    
    def test_execute_command_success(self):
        """Test successful command execution."""
        with patch.object(self.invoker.factory, 'create_command') as mock_create:
            command_mock = Mock()
            command_mock.execute.return_value = 0
            mock_create.return_value = command_mock
            
            args = Mock()
            
            result = self.invoker.execute_command('version', args)
            
            mock_create.assert_called_once_with('version')
            command_mock.execute.assert_called_once_with(args)
            assert result == 0
    
    def test_execute_command_not_found(self):
        """Test command execution when command is not found."""
        with patch.object(self.invoker.factory, 'create_command') as mock_create:
            with patch.object(self.invoker.factory, 'get_available_commands') as mock_get_commands:
                mock_create.return_value = None
                mock_get_commands.return_value = ['init', 'version', 'local']
                
                args = Mock()
                
                result = self.invoker.execute_command('unknown', args)
                
                mock_create.assert_called_once_with('unknown')
                self.logger_mock.error.assert_called_once()
                assert result == 1
    
    def test_execute_command_execution_failure(self):
        """Test command execution when execution fails."""
        with patch.object(self.invoker.factory, 'create_command') as mock_create:
            command_mock = Mock()
            command_mock.execute.return_value = 2
            mock_create.return_value = command_mock
            
            args = Mock()
            
            result = self.invoker.execute_command('init', args)
            
            mock_create.assert_called_once_with('init')
            command_mock.execute.assert_called_once_with(args)
            assert result == 2
    
    def test_execute_command_logs_invocation(self):
        """Test that command execution is logged."""
        with patch.object(self.invoker.factory, 'create_command') as mock_create:
            command_mock = Mock()
            command_mock.execute.return_value = 0
            mock_create.return_value = command_mock
            
            args = Mock()
            
            self.invoker.execute_command('version', args)
            
            # Check that invocation was logged
            calls = [call.args[0] for call in self.logger_mock.info.call_args_list]
            invocation_calls = [call for call in calls if "Command Invoker is called with command: version" in call]
            execution_calls = [call for call in calls if "Executing command: version" in call]
            
            assert len(invocation_calls) >= 1
            assert len(execution_calls) >= 1