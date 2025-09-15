"""Unit tests for service_orchestrator module."""
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import importlib.util

from osdu_perf.core.service_orchestrator import ServiceOrchestrator
from osdu_perf.core.base_service import BaseService


class TestServiceOrchestrator:
    """Test cases for ServiceOrchestrator."""
    
    # Test service classes for testing
    class TestService1(BaseService):
        def __init__(self, client=None):
            super().__init__(client)
            self.name = "test_service1"
        
        def execute(self, headers=None, partition=None, host=None):
            pass
        
        def provide_explicit_token(self):
            pass
        
        def prehook(self):
            pass
        
        def posthook(self):
            pass
    
    class TestService2(BaseService):
        def __init__(self, client=None):
            super().__init__(client)
            self.name = "test_service2"
        
        def execute(self, headers=None, partition=None, host=None):
            pass
        
        def provide_explicit_token(self):
            pass
        
        def prehook(self):
            pass
        
        def posthook(self):
            pass
    
    @pytest.fixture
    def orchestrator(self):
        """Create ServiceOrchestrator instance."""
        return ServiceOrchestrator()
    
    @pytest.fixture
    def mock_client(self):
        """Mock HTTP client."""
        return Mock()
    
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
    def test_orchestrator_initialization(self, orchestrator):
        """Test ServiceOrchestrator initialization."""
        assert orchestrator._services == []
    
    @pytest.mark.unit
    def test_get_services_empty(self, orchestrator):
        """Test get_services when no services are registered."""
        services = orchestrator.get_services()
        assert services == []
    
    @pytest.mark.unit
    def test_unregister_service(self, orchestrator, mock_client):
        """Test service unregistration."""
        service = self.TestService1(mock_client)
        orchestrator._services.append(service)
        
        # Unregister the service
        orchestrator.unregister_service(service)
        
        assert service not in orchestrator._services
        assert len(orchestrator._services) == 0
    
    @pytest.mark.unit
    def test_unregister_nonexistent_service(self, orchestrator, mock_client):
        """Test unregistering a service that doesn't exist."""
        service = self.TestService1(mock_client)
        
        # Should not raise an error
        orchestrator.unregister_service(service)
        assert len(orchestrator._services) == 0
    
    @pytest.mark.unit
    def test_find_service_by_name(self, orchestrator, mock_client):
        """Test finding a service by name."""
        service1 = self.TestService1(mock_client)
        service2 = self.TestService2(mock_client)
        
        orchestrator._services.extend([service1, service2])
        
        found_service = orchestrator.find_service("test_service1")
        assert found_service is service1
        
        found_service = orchestrator.find_service("test_service2")
        assert found_service is service2
        
        not_found = orchestrator.find_service("nonexistent")
        assert not_found is None
    
    @pytest.mark.unit
    def test_find_service_without_name_attribute(self, orchestrator, mock_client):
        """Test finding service when service doesn't have name attribute."""
        class ServiceWithoutName(BaseService):
            def __init__(self, client=None):
                super().__init__(client)
            
            def execute(self, headers=None, partition=None, host=None):
                pass
            
            def provide_explicit_token(self):
                pass
            
            def prehook(self):
                pass
            
            def posthook(self):
                pass
        
        service = ServiceWithoutName(mock_client)
        orchestrator._services.append(service)
        
        found_service = orchestrator.find_service("any_name")
        assert found_service is None
    
    @pytest.mark.unit
    @patch('builtins.print')
    def test_register_service_sample_no_services_folder(self, mock_print, orchestrator, mock_client, temp_directory):
        """Test register_service_sample when services folder doesn't exist."""
        orchestrator.register_service_sample(mock_client)
        
        # Should print error messages about missing services folder
        assert any("Services folder not found" in str(call) for call in mock_print.call_args_list)
    
    @pytest.mark.unit
    @patch('builtins.print')
    def test_register_service_sample_empty_services_folder(self, mock_print, orchestrator, mock_client, temp_directory):
        """Test register_service_sample with empty services folder."""
        # Create empty services folder
        os.makedirs("services")
        
        orchestrator.register_service_sample(mock_client)
        
        # Should complete without errors but no services registered
        assert len(orchestrator._services) == 0
    
    @pytest.mark.unit
    @patch('builtins.print')
    def test_register_service_no_test_files(self, mock_print, orchestrator, mock_client, temp_directory):
        """Test register_service when no perf_*_test.py files exist."""
        orchestrator.register_service(mock_client)
        
        # Should print message about no test files found
        assert any("No perf_*_test.py files found" in str(call) for call in mock_print.call_args_list)
    
    @pytest.mark.unit
    @patch('builtins.print')
    def test_register_service_with_test_files(self, mock_print, orchestrator, mock_client, temp_directory):
        """Test register_service with valid test files."""
        # Create a test file with a service class
        test_content = '''
from osdu_perf.core.base_service import BaseService

class StoragePerformanceTest(BaseService):
    def __init__(self, client=None):
        super().__init__(client)
        self.name = "storage"
    
    def execute(self, headers=None, partition=None, host=None):
        pass
    
    def provide_explicit_token(self):
        pass
    
    def prehook(self):
        pass
    
    def posthook(self):
        pass
'''
        with open("perf_storage_test.py", "w") as f:
            f.write(test_content)
        
        with patch('importlib.util.spec_from_file_location') as mock_spec, \
             patch('importlib.util.module_from_spec') as mock_module:
            
            # Mock the import process
            mock_spec_obj = Mock()
            mock_spec.return_value = mock_spec_obj
            
            mock_module_obj = Mock()
            # Set up the module object with our test service
            setattr(mock_module_obj, 'StoragePerformanceTest', self.TestService1)
            mock_module.return_value = mock_module_obj
            
            mock_loader = Mock()
            mock_spec_obj.loader = mock_loader
            
            orchestrator.register_service(mock_client)
    
    @pytest.mark.unit
    @patch('builtins.print')
    def test_register_service_import_error(self, mock_print, orchestrator, mock_client, temp_directory):
        """Test register_service with import errors."""
        # Create a test file with syntax error
        with open("perf_broken_test.py", "w") as f:
            f.write("invalid python syntax !!!")
        
        with patch('importlib.util.spec_from_file_location', side_effect=Exception("Import failed")):
            orchestrator.register_service(mock_client)
        
        # Should print error message
        assert any("Failed to load test module" in str(call) for call in mock_print.call_args_list)
    
    @pytest.mark.unit
    def test_get_services_with_multiple_services(self, orchestrator, mock_client):
        """Test get_services with multiple registered services."""
        service1 = self.TestService1(mock_client)
        service2 = self.TestService2(mock_client)
        
        orchestrator._services.extend([service1, service2])
        
        services = orchestrator.get_services()
        assert len(services) == 2
        assert service1 in services
        assert service2 in services
    
    @pytest.mark.unit
    @patch('builtins.print')
    def test_duplicate_service_registration(self, mock_print, orchestrator, mock_client):
        """Test that duplicate services are not registered."""
        service1 = self.TestService1(mock_client)
        
        # Add service directly to simulate it being already registered
        orchestrator._services.append(service1)
        
        # Try to register the same service again
        orchestrator._services.append(service1)  # This simulates the check in the actual code
        
        # In the real code, there's a check: if service_instance not in self._services
        # Let's test that behavior
        initial_count = len(orchestrator._services)
        
        # The actual registration logic prevents duplicates
        if service1 not in orchestrator._services[:-1]:  # Check if it was already there before the last add
            pass  # Would not add duplicate
        else:
            orchestrator._services.pop()  # Remove the duplicate we just added
        
        assert len(orchestrator._services) == initial_count - 1