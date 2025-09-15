"""Unit tests for core sample module."""
import pytest
import os
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from azure.identity import ManagedIdentityCredential, AzureCliCredential
from azure.core.exceptions import ClientAuthenticationError
from azure.core.credentials import AccessToken

from osdu_perf.core.sample import Auth


class TestAuth:
    """Test cases for Auth singleton class."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        Auth.reset_singleton()
        yield
        Auth.reset_singleton()
    
    @pytest.fixture
    def mock_access_token(self):
        """Mock access token."""
        return AccessToken(token="test-token", expires_on=time.time() + 3600)
    
    @pytest.mark.unit
    def test_singleton_behavior(self):
        """Test singleton behavior."""
        auth1 = Auth()
        auth2 = Auth()
        
        assert auth1 is auth2
        assert id(auth1) == id(auth2)
    
    @pytest.mark.unit
    @patch.dict(os.environ, {'IS_LOCAL': 'true'})
    @patch('osdu_perf.core.sample.AzureCliCredential')
    def test_initialization_local_environment(self, mock_cli_credential):
        """Test initialization in local environment."""
        mock_credential_instance = Mock()
        mock_cli_credential.return_value = mock_credential_instance
        
        auth = Auth()
        
        assert auth.credential is mock_credential_instance
        mock_cli_credential.assert_called_once()
    
    @pytest.mark.unit
    @patch.dict(os.environ, {'IS_LOCAL': 'false'})
    @patch('osdu_perf.core.sample.ManagedIdentityCredential')
    def test_initialization_azure_environment(self, mock_managed_credential):
        """Test initialization in Azure environment."""
        mock_credential_instance = Mock()
        mock_managed_credential.return_value = mock_credential_instance
        
        auth = Auth(client_id="test-client-id")
        
        assert auth.credential is mock_credential_instance
        mock_managed_credential.assert_called_once_with(client_id="test-client-id")
    
    @pytest.mark.unit
    @patch.dict(os.environ, {'IS_LOCAL': 'false'})
    @patch('osdu_perf.core.sample.ManagedIdentityCredential')
    def test_initialization_azure_environment_no_client_id(self, mock_managed_credential):
        """Test initialization in Azure environment without client ID."""
        mock_credential_instance = Mock()
        mock_managed_credential.return_value = mock_credential_instance
        
        auth = Auth()
        
        assert auth.credential is mock_credential_instance
        mock_managed_credential.assert_called_once_with()
    
    @pytest.mark.unit
    def test_is_running_locally_true(self):
        """Test _is_running_locally returns True for local environments."""
        local_values = ['true', '1', 'yes', 'on', 'TRUE', 'Yes', 'ON']
        
        for value in local_values:
            with patch.dict(os.environ, {'IS_LOCAL': value}):
                assert Auth._is_running_locally() is True
    
    @pytest.mark.unit
    def test_is_running_locally_false(self):
        """Test _is_running_locally returns False for non-local environments."""
        non_local_values = ['false', '0', 'no', 'off', 'FALSE', 'No', 'OFF', '']
        
        for value in non_local_values:
            with patch.dict(os.environ, {'IS_LOCAL': value}):
                assert Auth._is_running_locally() is False
        
        # Test with no environment variable
        with patch.dict(os.environ, {}, clear=True):
            assert Auth._is_running_locally() is False
    
    @pytest.mark.unit
    def test_get_bearer_token_success(self, mock_access_token):
        """Test successful token acquisition."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            
            with patch.object(auth.credential, 'get_token', return_value=mock_access_token):
                token = auth.get_bearer_token()
                
                assert token == "test-token"
                assert auth._cached_token == "test-token"
    
    @pytest.mark.unit
    def test_get_bearer_token_authentication_error(self):
        """Test token acquisition with authentication error."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            
            with patch.object(auth.credential, 'get_token', 
                            side_effect=ClientAuthenticationError("Auth failed")):
                with pytest.raises(ClientAuthenticationError):
                    auth.get_bearer_token()
                
                assert auth._cached_token is None
    
    @pytest.mark.unit
    def test_get_bearer_token_unexpected_error(self):
        """Test token acquisition with unexpected error."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            
            with patch.object(auth.credential, 'get_token', 
                            side_effect=Exception("Unexpected error")):
                with pytest.raises(Exception):
                    auth.get_bearer_token()
                
                assert auth._cached_token is None
    
    @pytest.mark.unit
    def test_token_caching(self, mock_access_token):
        """Test token caching functionality."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            
            with patch.object(auth.credential, 'get_token', return_value=mock_access_token) as mock_get:
                # First call
                token1 = auth.get_bearer_token()
                # Second call should use cache
                token2 = auth.get_bearer_token()
                
                assert token1 == token2 == "test-token"
                # Should only call get_token once due to caching
                assert mock_get.call_count == 1
    
    @pytest.mark.unit
    def test_token_cache_expiry(self):
        """Test token cache expiry and refresh."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth(refresh_buffer_seconds=1)
            
            # Create expired token
            expired_token = AccessToken(token="expired-token", expires_on=time.time() - 100)
            new_token = AccessToken(token="new-token", expires_on=time.time() + 3600)
            
            with patch.object(auth.credential, 'get_token', 
                            side_effect=[expired_token, new_token]) as mock_get:
                # First call with expired token
                token1 = auth.get_bearer_token()
                # Second call should refresh
                token2 = auth.get_bearer_token()
                
                assert token2 == "new-token"
                assert mock_get.call_count == 2
    
    @pytest.mark.unit
    def test_get_auth_headers(self, mock_access_token):
        """Test get_auth_headers method."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            
            with patch.object(auth.credential, 'get_token', return_value=mock_access_token):
                headers = auth.get_auth_headers()
                
                assert headers == {"Authorization": "Bearer test-token"}
    
    @pytest.mark.unit
    def test_invalidate_cache(self, mock_access_token):
        """Test manual cache invalidation."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            
            with patch.object(auth.credential, 'get_token', return_value=mock_access_token):
                # Get token to populate cache
                auth.get_bearer_token()
                assert auth._cached_token is not None
                
                # Invalidate cache
                auth.invalidate_cache()
                
                assert auth._cached_token is None
                assert auth._token_expiry_time == 0
    
    @pytest.mark.unit
    def test_is_token_valid(self, mock_access_token):
        """Test is_token_valid method."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth(refresh_buffer_seconds=300)
            
            # No token
            assert auth.is_token_valid() is False
            
            with patch.object(auth.credential, 'get_token', return_value=mock_access_token):
                # Get valid token
                auth.get_bearer_token()
                assert auth.is_token_valid() is True
    
    @pytest.mark.unit
    def test_get_token_info(self, mock_access_token):
        """Test get_token_info method."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            
            # No token
            info = auth.get_token_info()
            assert info["status"] == "no_token"
            assert info["expires_in_seconds"] == 0
            
            with patch.object(auth.credential, 'get_token', return_value=mock_access_token):
                # Get token
                auth.get_bearer_token()
                info = auth.get_token_info()
                
                assert info["status"] == "cached"
                assert "expires_in_seconds" in info
                assert "total_requests" in info
                assert "cache_hits" in info
                assert "cache_misses" in info
    
    @pytest.mark.unit
    def test_get_instance_class_method(self):
        """Test get_instance class method."""
        auth1 = Auth.get_instance(client_id="test-id")
        auth2 = Auth.get_instance()
        
        assert auth1 is auth2  # Should be same singleton instance
    
    @pytest.mark.unit
    def test_thread_safety_no_threading(self):
        """Test behavior when threading is not available."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            with patch('threading.RLock', side_effect=Exception("Threading unavailable")):
                auth = Auth()
                
                # Should work without threading
                assert auth._token_lock is None
    
    @pytest.mark.unit
    def test_fork_detection(self):
        """Test singleton reset on process fork."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            # Create instance in "parent" process
            auth1 = Auth()
            original_pid = Auth._pid
            
            # Simulate fork by changing PID
            with patch('os.getpid', return_value=original_pid + 1):
                auth2 = Auth()
                
                # Should be different instances due to fork detection
                assert Auth._pid == original_pid + 1
    
    @pytest.mark.unit
    def test_cleanup_on_exit(self):
        """Test cleanup method."""
        with patch.dict(os.environ, {'IS_LOCAL': 'true'}):
            auth = Auth()
            auth._cached_token = "test-token"
            auth._token_expiry_time = time.time() + 3600
            
            # Call cleanup
            auth._cleanup()
            
            # Token should be cleared
            assert auth._cached_token is None
            assert auth._token_expiry_time == 0