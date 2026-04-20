"""
Test cases for command base functionality.
"""
import pytest
from unittest.mock import Mock
from osdu_perf.cli.command_base import Command


class TestCommand:
    """Test cases for Command abstract base class."""
    
    def test_command_is_abstract(self):
        """Test that Command cannot be instantiated directly."""
        logger_mock = Mock()
        
        with pytest.raises(TypeError):
            Command(logger_mock)
    
    def test_concrete_command_implementation(self):
        """Test a concrete implementation of Command."""
        logger_mock = Mock()
        
        class ConcreteCommand(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                return 0
            
            def validate_args(self, args):
                return True
        
        command = ConcreteCommand(logger_mock)
        assert command.logger == logger_mock
    
    def test_handle_error_logs_and_returns_1(self):
        """Test that handle_error logs the error and returns 1."""
        logger_mock = Mock()
        
        class ConcreteCommand(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                return 0
            
            def validate_args(self, args):
                return True
        
        command = ConcreteCommand(logger_mock)
        test_error = Exception("Test error message")
        
        result = command.handle_error(test_error)
        
        logger_mock.error.assert_called_once_with("❌ Error: Test error message")
        assert result == 1
    
    def test_handle_error_with_different_exception_types(self):
        """Test handle_error with different exception types."""
        logger_mock = Mock()
        
        class ConcreteCommand(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                return 0
            
            def validate_args(self, args):
                return True
        
        command = ConcreteCommand(logger_mock)
        
        # Test with ValueError
        value_error = ValueError("Invalid value")
        result1 = command.handle_error(value_error)
        assert result1 == 1
        
        # Test with RuntimeError
        runtime_error = RuntimeError("Runtime issue")
        result2 = command.handle_error(runtime_error)
        assert result2 == 1
        
        # Check both errors were logged
        assert logger_mock.error.call_count == 2
        
        calls = [call.args[0] for call in logger_mock.error.call_args_list]
        assert "❌ Error: Invalid value" in calls
        assert "❌ Error: Runtime issue" in calls
    
    def test_abstract_methods_must_be_implemented(self):
        """Test that abstract methods must be implemented."""
        logger_mock = Mock()
        
        # Missing execute method
        class IncompleteCommand1(Command):
            def register_args(self, parser):
                pass

            def validate_args(self, args):
                return True
        
        with pytest.raises(TypeError):
            IncompleteCommand1(logger_mock)
        
        # Missing validate_args method
        class IncompleteCommand2(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                return 0
        
        with pytest.raises(TypeError):
            IncompleteCommand2(logger_mock)
        
        # Missing register_args method
        class IncompleteCommand3(Command):
            def execute(self, args):
                return 0

            def validate_args(self, args):
                return True
        
        with pytest.raises(TypeError):
            IncompleteCommand3(logger_mock)
    
    def test_command_inheritance_hierarchy(self):
        """Test the inheritance hierarchy works correctly."""
        logger_mock = Mock()
        
        class BaseConcreteCommand(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                return 0
            
            def validate_args(self, args):
                return True
            
            def custom_method(self):
                return "base"
        
        class ExtendedCommand(BaseConcreteCommand):
            def custom_method(self):
                return "extended"
        
        base_command = BaseConcreteCommand(logger_mock)
        extended_command = ExtendedCommand(logger_mock)
        
        assert isinstance(base_command, Command)
        assert isinstance(extended_command, Command)
        assert isinstance(extended_command, BaseConcreteCommand)
        
        assert base_command.custom_method() == "base"
        assert extended_command.custom_method() == "extended"
    
    def test_logger_assignment_during_initialization(self):
        """Test that logger is properly assigned during initialization."""
        logger_mock = Mock()
        logger_mock.name = "test_logger"
        
        class ConcreteCommand(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                self.logger.info("Executing command")
                return 0
            
            def validate_args(self, args):
                self.logger.debug("Validating args")
                return True
        
        command = ConcreteCommand(logger_mock)
        
        # Test that logger is accessible and functional
        args_mock = Mock()
        command.validate_args(args_mock)
        command.execute(args_mock)
        
        logger_mock.debug.assert_called_once_with("Validating args")
        logger_mock.info.assert_called_once_with("Executing command")
    
    def test_command_with_none_logger(self):
        """Test command behavior with None logger."""
        class ConcreteCommand(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                return 0
            
            def validate_args(self, args):
                return True
        
        # Should not raise an error
        command = ConcreteCommand(None)
        assert command.logger is None
        
        # handle_error should still work (will raise AttributeError when trying to call logger.error)
        with pytest.raises(AttributeError):
            command.handle_error(Exception("test"))
    
    def test_command_error_handling_preserves_exception_details(self):
        """Test that error handling preserves exception details."""
        logger_mock = Mock()
        
        class ConcreteCommand(Command):
            def register_args(self, parser):
                pass

            def execute(self, args):
                return 0
            
            def validate_args(self, args):
                return True
        
        command = ConcreteCommand(logger_mock)
        
        # Create an exception with specific details
        original_exception = ValueError("Specific error with details: 123")
        
        result = command.handle_error(original_exception)
        
        # Check that the full exception message is preserved
        logger_mock.error.assert_called_once_with("❌ Error: Specific error with details: 123")
        assert result == 1