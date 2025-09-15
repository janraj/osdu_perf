"""Unit tests for auth module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from azure.identity import AzureCliCredential, DefaultAzureCredential, ManagedIdentityCredential
from azure.core.exceptions import ClientAuthenticationError
from azure.core.credentials import AccessToken
import time

from osdu_perf.core.auth import AzureTokenManager


class TestAzureTokenManager:
    """Test cases for Azure Token Manager."""
    
    @pytest.fixture
    def token_manager(self):
        """Create token manager instance."""
        return AzureTokenManager(client_id="test-client-id")
    
    @pytest.mark.unit
    def test_initialization_with_managed_identity(self):
        """Test initialization with managed identity."""
        manager = AzureTokenManager(client_id="test-id", use_managed_identity=True)
        assert manager.client_id == "test-id"
        assert manager.use_managed_identity is True
        assert isinstance(manager._credential, ManagedIdentityCredential)
    
    @pytest.mark.unit
    def test_initialization_with_azure_cli(self):
        """Test initialization with Azure CLI credential."""
        with patch('osdu_perf.core.auth.AzureCliCredential'):
            manager = AzureTokenManager(use_managed_identity=False)
            assert manager.use_managed_identity is False
    
    @pytest.mark.unit
    def test_initialization_fallback_to_default(self):
        """Test fallback to DefaultAzureCredential."""
        with patch('osdu_perf.core.auth.AzureCliCredential', side_effect=Exception("CLI not available")):
            with patch('osdu_perf.core.auth.DefaultAzureCredential'):
                manager = AzureTokenManager(use_managed_identity=False)
                assert manager.use_managed_identity is False
    
    @pytest.mark.unit
    def test_get_access_token_success(self, token_manager, mock_access_token):
        """Test successful token acquisition."""
        with patch.object(token_manager._credential, 'get_token', return_value=mock_access_token):
            token = token_manager.get_access_token("https://management.azure.com/.default")
            assert token == "test-token"
    
    @pytest.mark.unit
    def test_get_access_token_with_client_id_scope(self, token_manager, mock_access_token):
        """Test token acquisition with client ID scope."""
        with patch.object(token_manager._credential, 'get_token', return_value=mock_access_token):
            token = token_manager.get_access_token()
            assert token == "test-token"
    
    @pytest.mark.unit
    def test_get_access_token_no_scope_no_client_id(self):
        """Test token acquisition without scope or client ID."""
        manager = AzureTokenManager()
        token = manager.get_access_token()
        assert token is None
    
    @pytest.mark.unit
    def test_get_access_token_authentication_error(self, token_manager):
        """Test authentication error handling."""
        with patch.object(token_manager._credential, 'get_token', 
                         side_effect=ClientAuthenticationError("Auth failed")):
            token = token_manager.get_access_token("test-scope")
            assert token is None
    
    @pytest.mark.unit
    def test_get_access_token_unexpected_error(self, token_manager):
        """Test unexpected error handling."""
        with patch.object(token_manager._credential, 'get_token', 
                         side_effect=Exception("Unexpected error")):
            token = token_manager.get_access_token("test-scope")
            assert token is None
    
    @pytest.mark.unit
    def test_token_caching(self, token_manager, mock_access_token):
        """Test token caching functionality."""
        with patch.object(token_manager._credential, 'get_token', return_value=mock_access_token) as mock_get:
            # First call
            token1 = token_manager.get_access_token("test-scope")
            # Second call should use cache
            token2 = token_manager.get_access_token("test-scope")
            
            assert token1 == token2 == "test-token"
            # Should only call get_token once due to caching
            assert mock_get.call_count == 1
    
    @pytest.mark.unit
    def test_token_cache_expiry(self, token_manager):
        """Test token cache expiry and refresh."""
        # Create expired token
        expired_token = AccessToken(token="expired-token", expires_on=time.time() - 100)
        new_token = AccessToken(token="new-token", expires_on=time.time() + 3600)
        
        with patch.object(token_manager._credential, 'get_token', 
                         side_effect=[expired_token, new_token]) as mock_get:
            # First call with expired token
            token1 = token_manager.get_access_token("test-scope")
            # Second call should refresh
            token2 = token_manager.get_access_token("test-scope")
            
            assert token2 == "new-token"
            assert mock_get.call_count == 2
    
    @pytest.mark.unit
    def test_get_auth_headers(self, token_manager, mock_access_token):
        """Test auth headers generation."""
        with patch.object(token_manager._credential, 'get_token', return_value=mock_access_token):
            headers = token_manager.get_auth_headers("test-scope")
            
            assert headers is not None
            assert headers["Authorization"] == "Bearer test-token"
            assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.unit
    def test_get_auth_headers_token_failure(self, token_manager):
        """Test auth headers when token acquisition fails."""
        with patch.object(token_manager._credential, 'get_token', 
                         side_effect=ClientAuthenticationError("Failed")):
            headers = token_manager.get_auth_headers("test-scope")
            assert headers is None
    
    @pytest.mark.unit
    def test_validate_token_access_success(self, token_manager, mock_access_token):
        """Test successful token validation."""
        with patch.object(token_manager._credential, 'get_token', return_value=mock_access_token):
            is_valid = token_manager.validate_token_access("test-scope")
            assert is_valid is True
    
    @pytest.mark.unit
    def test_validate_token_access_failure(self, token_manager):
        """Test token validation failure."""
        with patch.object(token_manager._credential, 'get_token', 
                         side_effect=ClientAuthenticationError("Failed")):
            is_valid = token_manager.validate_token_access("test-scope")
            assert is_valid is False
    
    @pytest.mark.unit
    def test_get_token_info_success(self, token_manager, mock_access_token):
        """Test token info retrieval."""
        with patch.object(token_manager._credential, 'get_token', return_value=mock_access_token):
            info = token_manager.get_token_info("test-scope")
            
            assert info is not None
            assert info["scope"] == "test-scope"
            assert "expires_in_seconds" in info
            assert "expires_in_minutes" in info
            assert "is_valid" in info
            assert "token_length" in info
            assert "credential_type" in info
    
    @pytest.mark.unit
    def test_get_token_info_no_scope_no_client_id(self):
        """Test token info without scope or client ID."""
        manager = AzureTokenManager()
        info = manager.get_token_info()
        assert info is None
    
    @pytest.mark.unit
    def test_get_token_info_failure(self, token_manager):
        """Test token info retrieval failure."""
        with patch.object(token_manager._credential, 'get_token', 
                         side_effect=Exception("Failed")):
            info = token_manager.get_token_info("test-scope")
            assert info is None
    
    @pytest.mark.unit
    def test_clear_token_cache(self, token_manager, mock_access_token):
        """Test token cache clearing."""
        with patch.object(token_manager._credential, 'get_token', return_value=mock_access_token):
            # Get token to populate cache
            token_manager.get_access_token("test-scope")
            
            # Clear cache
            token_manager.clear_token_cache()
            
            # Verify cache is cleared
            assert len(token_manager._cached_tokens) == 0