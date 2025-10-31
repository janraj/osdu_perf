"""
Test cases for logger utility.
"""
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from osdu_perf.utils.logger import OSDULogger, get_logger


class TestOSDULogger:
    """Test cases for OSDULogger class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Reset class state before each test
        OSDULogger._loggers.clear()
        OSDULogger._configured = False
    
    def test_get_logger_default_name(self):
        """Test getting logger with default name."""
        logger = OSDULogger.get_logger()
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'osdu_perf'
        assert 'osdu_perf' in OSDULogger._loggers
    
    def test_get_logger_custom_name(self):
        """Test getting logger with custom name."""
        logger = OSDULogger.get_logger('test_module')
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'osdu_perf.test_module'
        assert 'test_module' in OSDULogger._loggers
    
    def test_get_logger_caching(self):
        """Test that logger instances are cached."""
        logger1 = OSDULogger.get_logger('test_module')
        logger2 = OSDULogger.get_logger('test_module')
        
        assert logger1 is logger2
        assert len(OSDULogger._loggers) == 1
    
    def test_get_logger_multiple_names(self):
        """Test getting multiple loggers with different names."""
        logger1 = OSDULogger.get_logger('module1')
        logger2 = OSDULogger.get_logger('module2')
        logger3 = OSDULogger.get_logger()  # default name
        
        assert logger1.name == 'osdu_perf.module1'
        assert logger2.name == 'osdu_perf.module2'
        assert logger3.name == 'osdu_perf'
        assert len(OSDULogger._loggers) == 3
    
    def test_create_logger_root_name(self):
        """Test _create_logger with root name."""
        logger = OSDULogger._create_logger('osdu_perf')
        
        assert logger.name == 'osdu_perf'
        assert OSDULogger._configured is True
    
    def test_create_logger_child_name(self):
        """Test _create_logger with child name."""
        logger = OSDULogger._create_logger('test_module')
        
        assert logger.name == 'osdu_perf.test_module'
        assert OSDULogger._configured is True
    
    @patch('osdu_perf.utils.logger.logging.getLogger')
    def test_configure_logging_called_once(self, mock_get_logger):
        """Test that _configure_logging is called only once."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        with patch.object(OSDULogger, '_configure_logging') as mock_configure:
            # First call should configure
            OSDULogger._create_logger('test1')
            mock_configure.assert_called_once()
            
            # Second call should not configure again
            mock_configure.reset_mock()
            OSDULogger._create_logger('test2')
            mock_configure.assert_not_called()
    
    @patch('osdu_perf.utils.logger.logging.StreamHandler')
    @patch('osdu_perf.utils.logger.logging.Formatter')
    @patch('osdu_perf.utils.logger.logging.getLogger')
    def test_configure_logging_setup(self, mock_get_logger, mock_formatter, mock_handler):
        """Test _configure_logging sets up logging correctly."""
        mock_root_logger = Mock()
        mock_get_logger.return_value = mock_root_logger
        mock_formatter_instance = Mock()
        mock_formatter.return_value = mock_formatter_instance
        mock_handler_instance = Mock()
        mock_handler.return_value = mock_handler_instance
        
        OSDULogger._configure_logging()
        
        # Check formatter creation
        mock_formatter.assert_called_once()
        
        # Check handler creation and configuration
        mock_handler.assert_called_once()
        mock_handler_instance.setFormatter.assert_called_once_with(mock_formatter_instance)
        
        # Check root logger configuration
        mock_get_logger.assert_called_once_with('osdu_perf')
        mock_root_logger.setLevel.assert_called_once_with(logging.INFO)
        mock_root_logger.handlers.clear.assert_called_once()
        mock_root_logger.addHandler.assert_called_once_with(mock_handler_instance)
        assert mock_root_logger.propagate is False
    
    def test_logger_hierarchy(self):
        """Test that child loggers are properly configured."""
        parent_logger = OSDULogger.get_logger()
        child_logger = OSDULogger.get_logger('child')
        
        assert parent_logger.name == 'osdu_perf'
        assert child_logger.name == 'osdu_perf.child'
        
        # Child logger should inherit from parent
        assert child_logger.parent.name == 'osdu_perf'


class TestGetLogger:
    """Test cases for get_logger convenience function."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Reset class state before each test
        OSDULogger._loggers.clear()
        OSDULogger._configured = False
    
    def test_get_logger_function_default(self):
        """Test get_logger function with default name."""
        logger = get_logger()
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'osdu_perf'
    
    def test_get_logger_function_custom_name(self):
        """Test get_logger function with custom name."""
        logger = get_logger('test_module')
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'osdu_perf.test_module'
    
    def test_get_logger_function_none_name(self):
        """Test get_logger function with None name."""
        logger = get_logger(None)
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'osdu_perf'
    
    @patch.object(OSDULogger, 'get_logger')
    def test_get_logger_function_delegates(self, mock_osdu_get_logger):
        """Test that get_logger function delegates to OSDULogger.get_logger."""
        mock_logger = Mock()
        mock_osdu_get_logger.return_value = mock_logger
        
        result = get_logger('test_name')
        
        mock_osdu_get_logger.assert_called_once_with('test_name')
        assert result == mock_logger


class TestLoggerIntegration:
    """Integration tests for logger functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Reset class state before each test
        OSDULogger._loggers.clear()
        OSDULogger._configured = False
    
    def test_logger_can_log_messages(self):
        """Test that logger can actually log messages."""
        logger = get_logger('integration_test')
        
        # This should not raise any exceptions
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        logger.debug("Test debug message")
    
    def test_multiple_loggers_independent(self):
        """Test that multiple loggers work independently."""
        logger1 = get_logger('module1')
        logger2 = get_logger('module2')
        
        # Both should be able to log without interference
        logger1.info("Module 1 message")
        logger2.info("Module 2 message")
        
        assert logger1.name != logger2.name
        assert logger1 is not logger2
    
    def test_logger_level_inheritance(self):
        """Test that child loggers inherit level from parent."""
        parent_logger = get_logger()
        child_logger = get_logger('child')
        
        # Both should have INFO level (or inherit it)
        assert parent_logger.level == logging.INFO or parent_logger.getEffectiveLevel() == logging.INFO
        assert child_logger.getEffectiveLevel() == logging.INFO
    
    @patch('osdu_perf.utils.logger.sys.stdout')
    def test_logger_output_to_stdout(self, mock_stdout):
        """Test that logger outputs to stdout."""
        logger = get_logger('output_test')
        
        # Create a real StreamHandler to verify it uses stdout
        import sys
        from osdu_perf.utils.logger import logging
        
        # Get the actual handler from the logger
        root_logger = logging.getLogger('osdu_perf')
        handlers = root_logger.handlers
        
        # Should have at least one handler
        assert len(handlers) > 0
        
        # First handler should be a StreamHandler
        assert isinstance(handlers[0], logging.StreamHandler)
    
    def test_formatter_includes_required_fields(self):
        """Test that the formatter includes all required fields."""
        logger = get_logger('format_test')
        
        # Get the root logger and its handler
        root_logger = logging.getLogger('osdu_perf')
        handler = root_logger.handlers[0]
        formatter = handler.formatter
        
        # Create a test record
        record = logging.LogRecord(
            name='osdu_perf.format_test',
            level=logging.INFO,
            pathname='/test/path.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
            func='test_function'
        )
        
        formatted = formatter.format(record)
        
        # Check that all required fields are present
        assert 'osdu_perf.format_test' in formatted
        assert 'INFO' in formatted
        assert 'Test message' in formatted
        assert 'test_function' in formatted
        assert '42' in formatted
        assert 'path.py' in formatted