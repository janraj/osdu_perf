"""Unit tests for locust user_base module."""
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from locust import HttpUser, between

from osdu_perf.client_base.user_base import PerformanceUser
from osdu_perf.core.base_service import BaseService


class TestPerformanceUser:
    """Test cases for PerformanceUser."""
    
    # Test service for testing
    class MockService(BaseService):
        def __init__(self, client=None):
            super().__init__(client)
            self.name = "mock_service"
            self.execute_called = False
            self.prehook_called = False
            self.posthook_called = False
            self.token_provided = False
        
        def execute(self, headers=None, partition=None, base_url=None):
            self.execute_called = True
            self.last_headers = headers
            self.last_partition = partition
            self.last_base_url = base_url
        
        def provide_explicit_token(self):
            self.token_provided = True
            return "explicit-test-token"
        
        def prehook(self):
            self.prehook_called = True
        
        def posthook(self):
            self.posthook_called = True
    
    class MockServiceWithException(BaseService):
        def __init__(self, client=None):
            super().__init__(client)
            self.name = "failing_service"
        
        def execute(self, headers=None, partition=None, base_url=None):
            raise Exception("Service execution failed")
        
        def provide_explicit_token(self):
            raise Exception("Token provision failed")
        
        def prehook(self):
            raise Exception("Prehook failed")
        
        def posthook(self):
            raise Exception("Posthook failed")
    
    @pytest.fixture
    def mock_environment(self):
        """Mock Locust environment."""
        env = Mock()
        env.host = "https://test.osdu.com"
        env.parsed_options = Mock()
        env.parsed_options.partition = "test-partition"
        env.parsed_options.appid = "test-app-id"
        return env
    
    @pytest.fixture
    def mock_service_orchestrator(self):
        """Mock ServiceOrchestrator."""
        orchestrator = Mock()
        return orchestrator
    
    @pytest.fixture
    def mock_input_handler(self):
        """Mock InputHandler."""
        handler = Mock()
        handler.partition = "test-partition"
        handler.base_url = "https://test.osdu.com"
        handler.header = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
            "x-data-partition-id": "test-partition"
        }
        return handler
    
    @pytest.mark.unit
    def test_performance_user_inheritance(self):
        """Test PerformanceUser inherits from HttpUser."""
        assert issubclass(PerformanceUser, HttpUser)
    
    @pytest.mark.unit
    def test_performance_user_wait_time(self):
        """Test PerformanceUser has appropriate wait time."""
        # Check that wait_time is set and is callable (between function)
        assert hasattr(PerformanceUser, 'wait_time')
        # The wait_time should be a callable (between function)
        assert callable(PerformanceUser.wait_time)
    
    @pytest.mark.unit
    @patch('osdu_perf.locust.user_base.ServiceOrchestrator')
    def test_performance_user_initialization(self, mock_orchestrator_class, mock_environment):
        """Test PerformanceUser initialization."""
        mock_orchestrator_instance = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator_instance
        
        user = PerformanceUser(mock_environment)
        
        # Verify attributes are initialized
        assert user.service_orchestrator is mock_orchestrator_instance
        assert user.input_handler is None
        assert user.services == []
        assert isinstance(user.logger, logging.Logger)
        
        # Verify orchestrator was created
        mock_orchestrator_class.assert_called_once()
    
    @pytest.mark.unit
    @patch('osdu_perf.locust.user_base.InputHandler')
    @patch('osdu_perf.locust.user_base.ServiceOrchestrator')
    def test_on_start_method(self, mock_orchestrator_class, mock_input_handler_class, mock_environment):
        """Test on_start method."""
        # Setup mocks
        mock_orchestrator_instance = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator_instance
        mock_orchestrator_instance.get_services.return_value = []
        
        mock_input_handler_instance = Mock()
        mock_input_handler_class.return_value = mock_input_handler_instance
        
        user = PerformanceUser(mock_environment)
        user.client = Mock()  # Mock the HTTP client
        
        # Call on_start
        user.on_start()
        
        # Verify InputHandler was created
        mock_input_handler_class.assert_called_once_with(mock_environment)
        assert user.input_handler is mock_input_handler_instance
        
        # Verify services were registered and retrieved
        mock_orchestrator_instance.register_service.assert_called_once_with(user.client)
        mock_orchestrator_instance.get_services.assert_called_once()
        assert user.services == []
    
    @pytest.mark.unit
    @patch('osdu_perf.locust.user_base.InputHandler')
    @patch('osdu_perf.locust.user_base.ServiceOrchestrator')
    def test_execute_services_with_mock_service(self, mock_orchestrator_class, mock_input_handler_class, mock_environment):
        """Test execute_services with a mock service."""
        # Setup mocks
        mock_service = self.MockService()
        
        mock_orchestrator_instance = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator_instance
        
        mock_input_handler_instance = Mock()
        mock_input_handler_instance.partition = "test-partition"
        mock_input_handler_instance.base_url = "https://test.osdu.com"
        mock_input_handler_instance.header = {"Authorization": "Bearer test-token"}
        mock_input_handler_class.return_value = mock_input_handler_instance
        
        user = PerformanceUser(mock_environment)
        user.services = [mock_service]
        user.input_handler = mock_input_handler_instance
        
        # Execute services
        user.execute_services()
        
        # Verify service methods were called
        assert mock_service.prehook_called
        assert mock_service.execute_called
        assert mock_service.posthook_called
        assert mock_service.token_provided
        
        # Verify correct parameters were passed
        assert mock_service.last_partition == "test-partition"
        assert mock_service.last_base_url == "https://test.osdu.com"
        # Headers should include the explicit token
        assert "Authorization" in mock_service.last_headers
        assert mock_service.last_headers["Authorization"] == "Bearer explicit-test-token"
    
    @pytest.mark.unit
    @patch('osdu_perf.locust.user_base.InputHandler')
    @patch('osdu_perf.locust.user_base.ServiceOrchestrator')
    def test_execute_services_with_failing_service(self, mock_orchestrator_class, mock_input_handler_class, mock_environment):
        """Test execute_services with a service that raises exceptions."""
        # Setup mocks
        mock_service = self.MockServiceWithException()
        
        mock_orchestrator_instance = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator_instance
        
        mock_input_handler_instance = Mock()
        mock_input_handler_instance.partition = "test-partition"
        mock_input_handler_instance.base_url = "https://test.osdu.com"
        mock_input_handler_instance.header = {"Authorization": "Bearer test-token"}
        mock_input_handler_class.return_value = mock_input_handler_instance
        
        user = PerformanceUser(mock_environment)
        user.services = [mock_service]
        user.input_handler = mock_input_handler_instance
        
        # Mock logger to capture error messages
        user.logger = Mock()
        
        # Execute services - should not raise exceptions
        user.execute_services()
        
        # Verify logger was called for errors
        assert user.logger.error.call_count >= 1  # At least one error should be logged
    
    @pytest.mark.unit
    @patch('osdu_perf.locust.user_base.InputHandler')
    @patch('osdu_perf.locust.user_base.ServiceOrchestrator')
    def test_execute_services_service_without_methods(self, mock_orchestrator_class, mock_input_handler_class, mock_environment):
        """Test execute_services with service missing optional methods."""
        # Create a minimal service without optional methods
        class MinimalService:
            def execute(self, headers=None, partition=None, base_url=None):
                self.executed = True
        
        mock_service = MinimalService()
        
        mock_input_handler_instance = Mock()
        mock_input_handler_instance.partition = "test-partition"
        mock_input_handler_instance.base_url = "https://test.osdu.com"
        mock_input_handler_instance.header = {"Authorization": "Bearer test-token"}
        
        user = PerformanceUser(mock_environment)
        user.services = [mock_service]
        user.input_handler = mock_input_handler_instance
        
        # Execute services - should work without optional methods
        user.execute_services()
        
        # Verify execute was called
        assert hasattr(mock_service, 'executed')
        assert mock_service.executed
    
    @pytest.mark.unit
    @patch('osdu_perf.locust.user_base.InputHandler')
    @patch('osdu_perf.locust.user_base.ServiceOrchestrator')
    def test_execute_services_header_isolation(self, mock_orchestrator_class, mock_input_handler_class, mock_environment):
        """Test that header modifications don't affect other services."""
        # Create two services that modify headers
        class HeaderModifyingService(BaseService):
            def __init__(self, client=None, name="service"):
                super().__init__(client)
                self.name = name
                self.received_headers = None
            
            def execute(self, headers=None, partition=None, base_url=None):
                self.received_headers = headers.copy()
                headers["modified"] = f"by_{self.name}"
            
            def provide_explicit_token(self):
                return None
            
            def prehook(self):
                pass
            
            def posthook(self):
                pass
        
        service1 = HeaderModifyingService(name="service1")
        service2 = HeaderModifyingService(name="service2")
        
        mock_input_handler_instance = Mock()
        mock_input_handler_instance.partition = "test-partition"
        mock_input_handler_instance.base_url = "https://test.osdu.com"
        mock_input_handler_instance.header = {"Authorization": "Bearer test-token"}
        
        user = PerformanceUser(mock_environment)
        user.services = [service1, service2]
        user.input_handler = mock_input_handler_instance
        
        # Execute services
        user.execute_services()
        
        # Both services should receive the original headers
        assert "modified" not in service1.received_headers
        assert "modified" not in service2.received_headers
        assert service1.received_headers["Authorization"] == "Bearer test-token"
        assert service2.received_headers["Authorization"] == "Bearer test-token"