"""Unit tests for Template system."""
import pytest
from unittest.mock import Mock, patch, mock_open

from osdu_perf import (
    azure_loadtest_template,
    localdev_template,
    service_test_template
)


class TestAzureLoadTestTemplate:
    """Test cases for azure_loadtest_template module."""
    
    @pytest.mark.unit
    def test_get_azure_loadtest_template_structure(self):
        """Test azure_loadtest_template returns valid template."""
        template = azure_loadtest_template.get_azure_loadtest_template()
        
        # Verify it's a string
        assert isinstance(template, str)
        
        # Verify it contains key components
        assert 'AzureLoadTestManager' in template
        assert 'class' in template
        assert 'def' in template
        assert 'import' in template
    
    @pytest.mark.unit
    def test_azure_loadtest_template_contains_required_methods(self):
        """Test azure_loadtest_template contains required methods."""
        template = azure_loadtest_template.get_azure_loadtest_template()
        
        # Check for essential methods
        required_methods = [
            'authenticate',
            'find_test_files', 
            'detect_service_name',
            'create_or_get_loadtest_resource',
            'package_test_files',
            'upload_test_file',
            'create_load_test',
            'run_load_test',
            'upload_and_run_test'
        ]
        
        for method in required_methods:
            assert f'def {method}' in template, f"Missing method: {method}"
    
    @pytest.mark.unit
    def test_azure_loadtest_template_contains_imports(self):
        """Test azure_loadtest_template contains required imports."""
        template = azure_loadtest_template.get_azure_loadtest_template()
        
        # Check for essential imports
        required_imports = [
            'azure.identity',
            'azure.mgmt.loadtesting',
            'azure.mgmt.resource',
            'os',
            'glob',
            'tempfile',
            'zipfile',
            'datetime'
        ]
        
        for import_stmt in required_imports:
            assert import_stmt in template, f"Missing import: {import_stmt}"


class TestLocalDevTemplate:
    """Test cases for localdev_template module."""
    
    @pytest.mark.unit
    def test_get_localdev_template_structure(self):
        """Test localdev_template returns valid template."""
        template = localdev_template.get_localdev_template()
        
        # Verify it's a string
        assert isinstance(template, str)
        
        # Verify it contains key components for Locust
        assert 'from locust' in template
        assert 'class' in template
        assert 'OSDUUser' in template or 'PerformanceUser' in template
        assert 'def' in template
    
    @pytest.mark.unit
    def test_localdev_template_contains_osdu_integration(self):
        """Test localdev_template contains OSDU-specific integration."""
        template = localdev_template.get_localdev_template()
        
        # Check for OSDU-specific components
        osdu_components = [
            'InputHandler',
            'ServiceOrchestrator', 
            'partition',
            'headers',
            'base_url'
        ]
        
        for component in osdu_components:
            assert component in template, f"Missing OSDU component: {component}"
    
    @pytest.mark.unit
    def test_localdev_template_contains_locust_structure(self):
        """Test localdev_template contains proper Locust structure."""
        template = localdev_template.get_localdev_template()
        
        # Check for Locust-specific components
        locust_components = [
            'HttpUser',
            'task',
            'on_start',
            'client'
        ]
        
        for component in locust_components:
            assert component in template, f"Missing Locust component: {component}"
    
    @pytest.mark.unit
    def test_localdev_template_environment_variables(self):
        """Test localdev_template handles environment variables."""
        template = localdev_template.get_localdev_template()
        
        # Check for environment variable handling
        env_vars = [
            'OSDU_HOST',
            'OSDU_PARTITION', 
            'ADME_BEARER_TOKEN'
        ]
        
        for env_var in env_vars:
            assert env_var in template, f"Missing environment variable: {env_var}"


class TestServiceTestTemplate:
    """Test cases for service_test_template module."""
    
    @pytest.mark.unit
    def test_get_service_template_structure(self):
        """Test service_test_template returns valid template."""
        template = service_test_template.get_service_template('storage')
        
        # Verify it's a string
        assert isinstance(template, str)
        
        # Verify it contains key components
        assert 'class' in template
        assert 'BaseService' in template
        assert 'def execute' in template
        assert 'storage' in template.lower()
    
    @pytest.mark.unit
    def test_service_template_customization(self):
        """Test service_test_template customizes for different services."""
        services = ['storage', 'search', 'wellbore', 'schema']
        
        for service in services:
            template = service_test_template.get_service_template(service)
            
            # Should contain service-specific naming
            assert service.lower() in template.lower()
            
            # Should contain class with service name
            assert f'{service.title()}PerformanceTest' in template or f'{service}' in template
    
    @pytest.mark.unit
    def test_service_template_base_structure(self):
        """Test service_test_template contains proper base structure."""
        template = service_test_template.get_service_template('storage')
        
        # Check for base class components
        required_components = [
            'from osdu_perf',
            'BaseService',
            '__init__',
            'def execute',
            'self.client',
            'headers',
            'partition',
            'base_url'
        ]
        
        for component in required_components:
            assert component in template, f"Missing component: {component}"
    
    @pytest.mark.unit
    def test_service_template_example_requests(self):
        """Test service_test_template contains example HTTP requests."""
        template = service_test_template.get_service_template('storage')
        
        # Check for HTTP request examples
        http_methods = [
            'self.client.get',
            'self.client.post'
        ]
        
        # At least one HTTP method should be present
        assert any(method in template for method in http_methods)
        
        # Should contain request naming for Locust stats
        assert 'name=' in template


class TestTemplateSystemIntegration:
    """Test cases for template system integration and consistency."""
    
    @pytest.mark.unit
    def test_all_templates_are_valid_python(self):
        """Test that all templates generate syntactically valid Python."""
        # Test azure loadtest template
        azure_template = azure_loadtest_template.get_azure_loadtest_template()
        try:
            compile(azure_template, '<string>', 'exec')
        except SyntaxError as e:
            pytest.fail(f"Azure loadtest template has syntax error: {e}")
        
        # Test localdev template  
        local_template = localdev_template.get_localdev_template()
        try:
            compile(local_template, '<string>', 'exec')
        except SyntaxError as e:
            pytest.fail(f"Local dev template has syntax error: {e}")
        
        # Test service template
        service_template_code = service_test_template.get_service_template('storage')
        try:
            compile(service_template_code, '<string>', 'exec')
        except SyntaxError as e:
            pytest.fail(f"Service template has syntax error: {e}")
    
    @pytest.mark.unit
    def test_template_consistency(self):
        """Test that templates use consistent naming and imports."""
        templates = {
            'azure': azure_loadtest_template.get_azure_loadtest_template(),
            'local': localdev_template.get_localdev_template(),
            'service': service_test_template.get_service_template('storage')
        }
        
        # Check for consistent OSDU partition variable naming
        partition_vars = ['partition', 'OSDU_PARTITION']
        for template_name, template in templates.items():
            if template_name != 'azure':  # Azure template may not have these
                has_partition = any(var in template for var in partition_vars)
                assert has_partition, f"{template_name} template missing partition variables"
    
    @pytest.mark.unit
    def test_template_file_encoding(self):
        """Test that templates handle proper file encoding."""
        # All templates should be UTF-8 compatible strings
        templates = [
            azure_loadtest_template.get_azure_loadtest_template(),
            localdev_template.get_localdev_template(), 
            service_test_template.get_service_template('storage')
        ]
        
        for i, template in enumerate(templates):
            try:
                template.encode('utf-8')
            except UnicodeEncodeError:
                pytest.fail(f"Template {i} cannot be encoded as UTF-8")
    
    @pytest.mark.unit
    def test_template_length_reasonable(self):
        """Test that templates are reasonable length (not empty, not excessive)."""
        templates = {
            'azure': azure_loadtest_template.get_azure_loadtest_template(),
            'local': localdev_template.get_localdev_template(),
            'service': service_test_template.get_service_template('storage')
        }
        
        for name, template in templates.items():
            # Should not be empty
            assert len(template) > 100, f"{name} template is too short"
            
            # Should not be excessively long (likely indicates an error)
            assert len(template) < 50000, f"{name} template is too long"
            
            # Should have reasonable line count
            line_count = len(template.split('\n'))
            assert 10 < line_count < 1000, f"{name} template has unreasonable line count: {line_count}"


class TestTemplateErrorHandling:
    """Test cases for template error handling and edge cases."""
    
    @pytest.mark.unit
    def test_service_template_invalid_service(self):
        """Test service_test_template with edge case service names."""
        # Test with various service name formats
        edge_cases = ['', 'UPPERCASE', 'mixed-Case', 'service_with_underscores', 'service-with-hyphens']
        
        for service in edge_cases:
            try:
                template = service_test_template.get_service_template(service)
                # Should still return a string
                assert isinstance(template, str)
                assert len(template) > 0
            except Exception as e:
                # If it fails, it should fail gracefully
                assert "service" in str(e).lower()
    
    @pytest.mark.unit
    def test_template_functions_exist(self):
        """Test that all template functions are callable."""
        # Test all template functions exist and are callable
        assert callable(azure_loadtest_template.get_azure_loadtest_template)
        assert callable(localdev_template.get_localdev_template)
        assert callable(service_test_template.get_service_template)
    
    @pytest.mark.unit
    def test_template_import_structure(self):
        """Test that templates can be imported without circular imports."""
        # This test ensures the template modules can be imported cleanly
        try:
            import osdu_perf.azure_loadtest_template
            import osdu_perf.localdev_template
            import osdu_perf.service_test_template
        except ImportError as e:
            pytest.fail(f"Template import failed: {e}")