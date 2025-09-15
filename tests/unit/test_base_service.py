"""Unit tests for base_service module."""
import pytest
from unittest.mock import Mock, patch
from abc import ABC

from osdu_perf.core.base_service import BaseService


class TestBaseService:
    """Test cases for BaseService abstract class."""
    
    class ConcreteService(BaseService):
        """Concrete implementation for testing."""
        
        def execute(self, headers=None, partition=None, host=None):
            """Test implementation of execute method."""
            return f"Executed with headers={headers}, partition={partition}, host={host}"
        
        def provide_explicit_token(self):
            """Test implementation of provide_explicit_token method."""
            return "test-token"
        
        def prehook(self):
            """Test implementation of prehook method."""
            return "prehook executed"
        
        def posthook(self):
            """Test implementation of posthook method."""
            return "posthook executed"
    
    class IncompleteService(BaseService):
        """Incomplete implementation for testing abstract method enforcement."""
        pass
    
    @pytest.fixture
    def mock_client(self):
        """Mock HTTP client."""
        client = Mock()
        client.get = Mock(return_value=Mock(status_code=200))
        client.post = Mock(return_value=Mock(status_code=201))
        return client
    
    @pytest.mark.unit
    def test_concrete_service_initialization(self, mock_client):
        """Test concrete service initialization."""
        service = self.ConcreteService(client=mock_client)
        assert service.client == mock_client
    
    @pytest.mark.unit
    def test_concrete_service_initialization_without_client(self):
        """Test concrete service initialization without client."""
        service = self.ConcreteService()
        assert service.client is None
    
    @pytest.mark.unit
    def test_concrete_service_execute(self, mock_client):
        """Test concrete service execute method."""
        service = self.ConcreteService(client=mock_client)
        result = service.execute(
            headers={"Authorization": "Bearer token"},
            partition="test-partition",
            host="https://test.com"
        )
        
        expected = "Executed with headers={'Authorization': 'Bearer token'}, partition=test-partition, host=https://test.com"
        assert result == expected
    
    @pytest.mark.unit
    def test_concrete_service_provide_explicit_token(self, mock_client):
        """Test concrete service provide_explicit_token method."""
        service = self.ConcreteService(client=mock_client)
        token = service.provide_explicit_token()
        assert token == "test-token"
    
    @pytest.mark.unit
    def test_concrete_service_prehook(self, mock_client):
        """Test concrete service prehook method."""
        service = self.ConcreteService(client=mock_client)
        result = service.prehook()
        assert result == "prehook executed"
    
    @pytest.mark.unit
    def test_concrete_service_posthook(self, mock_client):
        """Test concrete service posthook method."""
        service = self.ConcreteService(client=mock_client)
        result = service.posthook()
        assert result == "posthook executed"
    
    @pytest.mark.unit
    def test_base_service_is_abstract(self):
        """Test that BaseService is abstract."""
        assert issubclass(BaseService, ABC)
    
    @pytest.mark.unit
    def test_incomplete_service_cannot_be_instantiated(self):
        """Test that incomplete service cannot be instantiated."""
        with pytest.raises(TypeError):
            self.IncompleteService()
    
    @pytest.mark.unit
    def test_abstract_methods_exist(self):
        """Test that all expected abstract methods exist."""
        abstract_methods = BaseService.__abstractmethods__
        expected_methods = {'execute', 'provide_explicit_token', 'prehook', 'posthook'}
        assert abstract_methods == expected_methods
    
    @pytest.mark.unit
    def test_service_with_client_operations(self, mock_client):
        """Test service operations with client."""
        service = self.ConcreteService(client=mock_client)
        
        # Test that client can be used for HTTP operations
        service.client.get("https://test.com/api")
        service.client.post("https://test.com/api", json={"test": "data"})
        
        # Verify client methods were called
        mock_client.get.assert_called_once_with("https://test.com/api")
        mock_client.post.assert_called_once_with("https://test.com/api", json={"test": "data"})


class TestBaseServiceInheritance:
    """Test cases for BaseService inheritance patterns."""
    
    class MinimalService(BaseService):
        """Minimal implementation with required methods."""
        
        def __init__(self, client=None, name="minimal"):
            super().__init__(client)
            self.name = name
        
        def execute(self, headers=None, partition=None, host=None):
            return {"status": "executed", "name": self.name}
        
        def provide_explicit_token(self):
            return None
        
        def prehook(self):
            pass
        
        def posthook(self):
            pass
    
    @pytest.mark.unit
    def test_minimal_service_inheritance(self):
        """Test minimal service inheritance."""
        service = self.MinimalService(name="test-service")
        assert isinstance(service, BaseService)
        assert service.name == "test-service"
    
    @pytest.mark.unit
    def test_minimal_service_execute(self):
        """Test minimal service execute method."""
        service = self.MinimalService(name="test-service")
        result = service.execute(headers={"test": "header"})
        
        assert result["status"] == "executed"
        assert result["name"] == "test-service"
    
    @pytest.mark.unit
    def test_minimal_service_hooks_return_none(self):
        """Test minimal service hooks return None."""
        service = self.MinimalService()
        
        assert service.prehook() is None
        assert service.posthook() is None
        assert service.provide_explicit_token() is None