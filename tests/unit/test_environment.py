"""Unit tests for utils environment module."""
import pytest
import os
from unittest.mock import patch

from osdu_perf.utils.environment import detect_environment, get_environment_config


class TestEnvironmentUtils:
    """Test cases for environment utilities."""
    
    @pytest.mark.unit
    def test_detect_environment_default(self):
        """Test detect_environment returns dev by default."""
        with patch.dict(os.environ, {}, clear=True):
            env = detect_environment()
            assert env == 'dev'
    
    @pytest.mark.unit
    def test_detect_environment_dev_values(self):
        """Test detect_environment with various dev values."""
        dev_values = ['dev', 'development', 'DEV', 'DEVELOPMENT', 'Dev', 'Development']
        
        for value in dev_values:
            with patch.dict(os.environ, {'ENVIRONMENT': value}, clear=True):
                env = detect_environment()
                assert env == 'dev', f"Failed for value: {value}"
    
    @pytest.mark.unit
    def test_detect_environment_staging_values(self):
        """Test detect_environment with various staging values."""
        staging_values = ['staging', 'stage', 'STAGING', 'STAGE', 'Staging', 'Stage']
        
        for value in staging_values:
            with patch.dict(os.environ, {'ENVIRONMENT': value}, clear=True):
                env = detect_environment()
                assert env == 'staging', f"Failed for value: {value}"
    
    @pytest.mark.unit
    def test_detect_environment_prod_values(self):
        """Test detect_environment with various production values."""
        prod_values = ['prod', 'production', 'PROD', 'PRODUCTION', 'Prod', 'Production']
        
        for value in prod_values:
            with patch.dict(os.environ, {'ENVIRONMENT': value}, clear=True):
                env = detect_environment()
                assert env == 'prod', f"Failed for value: {value}"
    
    @pytest.mark.unit
    def test_detect_environment_unknown_value(self):
        """Test detect_environment with unknown environment value."""
        unknown_values = ['test', 'unknown', 'local', 'custom']
        
        for value in unknown_values:
            with patch.dict(os.environ, {'ENVIRONMENT': value}, clear=True):
                env = detect_environment()
                assert env == 'dev', f"Failed for value: {value}, should default to dev"
    
    @pytest.mark.unit
    def test_detect_environment_empty_string(self):
        """Test detect_environment with empty environment variable."""
        with patch.dict(os.environ, {'ENVIRONMENT': ''}, clear=True):
            env = detect_environment()
            assert env == 'dev'
    
    @pytest.mark.unit
    def test_get_environment_config_dev(self):
        """Test get_environment_config for dev environment."""
        with patch('osdu_perf.utils.environment.detect_environment', return_value='dev'):
            config = get_environment_config()
            
            expected = {
                'use_managed_identity': False,
                'log_level': 'DEBUG',
                'timeout': 30,
            }
            
            assert config == expected
    
    @pytest.mark.unit
    def test_get_environment_config_staging(self):
        """Test get_environment_config for staging environment."""
        with patch('osdu_perf.utils.environment.detect_environment', return_value='staging'):
            config = get_environment_config()
            
            expected = {
                'use_managed_identity': True,
                'log_level': 'INFO',
                'timeout': 60,
            }
            
            assert config == expected
    
    @pytest.mark.unit
    def test_get_environment_config_prod(self):
        """Test get_environment_config for prod environment."""
        with patch('osdu_perf.utils.environment.detect_environment', return_value='prod'):
            config = get_environment_config()
            
            expected = {
                'use_managed_identity': True,
                'log_level': 'WARNING',
                'timeout': 120,
            }
            
            assert config == expected
    
    @pytest.mark.unit
    def test_get_environment_config_unknown_environment(self):
        """Test get_environment_config for unknown environment defaults to dev."""
        with patch('osdu_perf.utils.environment.detect_environment', return_value='unknown'):
            config = get_environment_config()
            
            # Should return dev config for unknown environment
            expected = {
                'use_managed_identity': False,
                'log_level': 'DEBUG',
                'timeout': 30,
            }
            
            assert config == expected
    
    @pytest.mark.unit
    def test_environment_config_structure(self):
        """Test that environment config has expected structure."""
        config = get_environment_config()
        
        # Verify required keys exist
        required_keys = {'use_managed_identity', 'log_level', 'timeout'}
        assert set(config.keys()) == required_keys
        
        # Verify types
        assert isinstance(config['use_managed_identity'], bool)
        assert isinstance(config['log_level'], str)
        assert isinstance(config['timeout'], int)
    
    @pytest.mark.unit
    def test_config_values_are_different_per_environment(self):
        """Test that different environments have different config values."""
        with patch('osdu_perf.utils.environment.detect_environment', return_value='dev'):
            dev_config = get_environment_config()
        
        with patch('osdu_perf.utils.environment.detect_environment', return_value='staging'):
            staging_config = get_environment_config()
        
        with patch('osdu_perf.utils.environment.detect_environment', return_value='prod'):
            prod_config = get_environment_config()
        
        # Configs should be different
        assert dev_config != staging_config
        assert staging_config != prod_config
        assert dev_config != prod_config
        
        # Verify specific differences
        assert dev_config['use_managed_identity'] is False
        assert staging_config['use_managed_identity'] is True
        assert prod_config['use_managed_identity'] is True
        
        assert dev_config['timeout'] < staging_config['timeout'] < prod_config['timeout']
    
    @pytest.mark.unit
    def test_integration_detect_and_config(self):
        """Test integration between detect_environment and get_environment_config."""
        test_cases = [
            ('dev', {'use_managed_identity': False, 'log_level': 'DEBUG', 'timeout': 30}),
            ('staging', {'use_managed_identity': True, 'log_level': 'INFO', 'timeout': 60}),
            ('prod', {'use_managed_identity': True, 'log_level': 'WARNING', 'timeout': 120}),
        ]
        
        for env_value, expected_config in test_cases:
            with patch.dict(os.environ, {'ENVIRONMENT': env_value}, clear=True):
                detected_env = detect_environment()
                config = get_environment_config()
                
                assert detected_env == env_value
                assert config == expected_config