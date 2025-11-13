"""
Test cases for user base performance testing classes.
"""
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from osdu_perf.locust_integration.user_base import PerformanceUser


class TestPerformanceUser:
    """Test cases for PerformanceUser class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Reset class-level variables
        PerformanceUser._kusto_config = None
        PerformanceUser._input_handler_instance = None
    
    def test_class_attributes(self):
        """Test that PerformanceUser has required class attributes."""
        assert PerformanceUser.abstract is True
        assert hasattr(PerformanceUser, 'wait_time')
        assert PerformanceUser.host == "https://localhost"
        assert hasattr(PerformanceUser, '_kusto_config')
        assert hasattr(PerformanceUser, '_input_handler_instance')
    
    @patch('osdu_perf.locust_integration.user_base.ServiceOrchestrator')
    def test_initialization(self, mock_service_orchestrator):
        """Test PerformanceUser initialization."""
        mock_environment = Mock()
        mock_orchestrator_instance = Mock()
        mock_service_orchestrator.return_value = mock_orchestrator_instance
        
        user = PerformanceUser(mock_environment)
        
        # Check initialization
        assert user.service_orchestrator is mock_orchestrator_instance
        assert user.input_handler is None
        assert user.services == []
        assert hasattr(user, 'logger')
        assert isinstance(user.logger, logging.Logger)
    
    def test_setup_logging_creates_logger(self):
        """Test that _setup_logging creates a proper logger."""
        logger = PerformanceUser._setup_logging()
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'osdu_perf.locust_integration.user_base'
    
    @patch('osdu_perf.locust_integration.user_base.logging.getLogger')
    def test_setup_logging_configuration(self, mock_get_logger):
        """Test that _setup_logging configures logger properly."""
        mock_logger = Mock()
        mock_logger.handlers = []  # No existing handlers
        mock_get_logger.return_value = mock_logger
        
        with patch('osdu_perf.locust_integration.user_base.logging.StreamHandler') as mock_handler_class:
            with patch('osdu_perf.locust_integration.user_base.logging.Formatter') as mock_formatter_class:
                mock_handler = Mock()
                mock_formatter = Mock()
                mock_handler_class.return_value = mock_handler
                mock_formatter_class.return_value = mock_formatter
                
                result = PerformanceUser._setup_logging()
                
                # Verify logger configuration
                mock_formatter_class.assert_called_once()
                mock_handler.setFormatter.assert_called_once_with(mock_formatter)
                mock_logger.addHandler.assert_called_once_with(mock_handler)
                mock_logger.setLevel.assert_called_once_with(logging.INFO)
                assert result is mock_logger
    
    @patch('osdu_perf.locust_integration.user_base.logging.getLogger')
    def test_setup_logging_existing_handlers(self, mock_get_logger):
        """Test that _setup_logging doesn't reconfigure logger with existing handlers."""
        mock_logger = Mock()
        mock_logger.handlers = [Mock()]  # Existing handler
        mock_get_logger.return_value = mock_logger
        
        result = PerformanceUser._setup_logging()
        
        # Should not add new handlers
        mock_logger.addHandler.assert_not_called()
        mock_logger.setLevel.assert_not_called()
        assert result is mock_logger
    
    def test_kusto_config_class_variable(self):
        """Test that _kusto_config class variable works properly."""
        # Initially should be None
        assert PerformanceUser._kusto_config is None
        
        # Set a value
        test_config = {"test": "config"}
        PerformanceUser._kusto_config = test_config
        
        # Should be accessible
        assert PerformanceUser._kusto_config == test_config
        
        # Should be shared across instances
        mock_env = Mock()
        with patch('osdu_perf.locust_integration.user_base.ServiceOrchestrator'):
            user1 = PerformanceUser(mock_env)
            user2 = PerformanceUser(mock_env)
            
            assert user1._kusto_config == test_config
            assert user2._kusto_config == test_config
    
    def test_input_handler_instance_class_variable(self):
        """Test that _input_handler_instance class variable works properly."""
        # Initially should be None
        assert PerformanceUser._input_handler_instance is None
        
        # Set a value
        test_handler = Mock()
        PerformanceUser._input_handler_instance = test_handler
        
        # Should be accessible
        assert PerformanceUser._input_handler_instance == test_handler
        
        # Should be shared across instances
        mock_env = Mock()
        with patch('osdu_perf.locust_integration.user_base.ServiceOrchestrator'):
            user1 = PerformanceUser(mock_env)
            user2 = PerformanceUser(mock_env)
            
            assert user1._input_handler_instance == test_handler
            assert user2._input_handler_instance == test_handler
    
    @patch('osdu_perf.locust_integration.user_base.ServiceOrchestrator')
    def test_services_list_initialization(self, mock_service_orchestrator):
        """Test that services list is properly initialized."""
        mock_environment = Mock()
        mock_orchestrator_instance = Mock()
        mock_service_orchestrator.return_value = mock_orchestrator_instance
        
        user = PerformanceUser(mock_environment)
        
        assert isinstance(user.services, list)
        assert len(user.services) == 0
        
        # Should be instance-specific
        user2 = PerformanceUser(mock_environment)
        user.services.append("test_service")
        
        assert len(user.services) == 1
        assert len(user2.services) == 0
    
    @patch('osdu_perf.locust_integration.user_base.ServiceOrchestrator')
    def test_service_orchestrator_creation(self, mock_service_orchestrator):
        """Test that ServiceOrchestrator is properly created."""
        mock_environment = Mock()
        mock_orchestrator_instance = Mock()
        mock_service_orchestrator.return_value = mock_orchestrator_instance
        
        user = PerformanceUser(mock_environment)
        
        mock_service_orchestrator.assert_called_once()
        assert user.service_orchestrator is mock_orchestrator_instance
    
    def test_abstract_class_property(self):
        """Test that PerformanceUser is marked as abstract."""
        assert PerformanceUser.abstract is True
        
        # This indicates it's meant to be inherited, not used directly
        # The abstract property is used by Locust to prevent direct instantiation
    
    def test_default_host_configuration(self):
        """Test that default host is properly configured."""
        assert PerformanceUser.host == "https://localhost"
        
        # Should be modifiable for testing
        original_host = PerformanceUser.host
        PerformanceUser.host = "https://test.example.com"
        assert PerformanceUser.host == "https://test.example.com"
        
        # Restore original value
        PerformanceUser.host = original_host
    
    def test_wait_time_configuration(self):
        """Test that wait_time is properly configured."""
        assert hasattr(PerformanceUser, 'wait_time')
        
        # wait_time should be callable (it's a between() function)
        assert callable(PerformanceUser.wait_time)
    
    @patch('osdu_perf.locust_integration.user_base.ServiceOrchestrator')
    def test_multiple_instance_isolation(self, mock_service_orchestrator):
        """Test that multiple instances are properly isolated."""
        mock_environment = Mock()
        mock_orchestrator_instance1 = Mock()
        mock_orchestrator_instance2 = Mock()
        mock_service_orchestrator.side_effect = [mock_orchestrator_instance1, mock_orchestrator_instance2]
        
        user1 = PerformanceUser(mock_environment)
        user2 = PerformanceUser(mock_environment)
        
        # Each should have its own orchestrator instance
        assert user1.service_orchestrator is mock_orchestrator_instance1
        assert user2.service_orchestrator is mock_orchestrator_instance2
        assert user1.service_orchestrator is not user2.service_orchestrator
        
        # But they should share class-level variables
        assert user1._kusto_config is user2._kusto_config
        assert user1._input_handler_instance is user2._input_handler_instance


class TestPerformanceUserLogging:
    """Test logging-specific functionality."""
    
    def test_logging_format(self):
        """Test that logging format is correctly configured."""
        with patch('osdu_perf.locust_integration.user_base.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_logger.handlers = []
            mock_get_logger.return_value = mock_logger
            
            with patch('osdu_perf.locust_integration.user_base.logging.Formatter') as mock_formatter:
                with patch('osdu_perf.locust_integration.user_base.logging.StreamHandler'):
                    PerformanceUser._setup_logging()
                    
                    # Check that formatter was called with correct format
                    mock_formatter.assert_called_once()
                    format_string = mock_formatter.call_args[0][0]
                    
                    # Check that format includes expected components
                    assert '%(asctime)s' in format_string
                    assert '%(name)s' in format_string
                    assert '%(filename)s' in format_string
                    assert '%(funcName)s' in format_string
                    assert '%(lineno)d' in format_string
                    assert '%(levelname)s' in format_string
                    assert '%(message)s' in format_string
    
    def test_logging_level(self):
        """Test that logging level is set to INFO."""
        with patch('osdu_perf.locust_integration.user_base.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_logger.handlers = []
            mock_get_logger.return_value = mock_logger
            
            with patch('osdu_perf.locust_integration.user_base.logging.StreamHandler'):
                with patch('osdu_perf.locust_integration.user_base.logging.Formatter'):
                    PerformanceUser._setup_logging()
                    
                    mock_logger.setLevel.assert_called_once_with(logging.INFO)