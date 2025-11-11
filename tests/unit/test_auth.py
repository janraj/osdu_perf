"""
Test cases for Azure authentication module.
"""
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from osdu_perf.core.auth import AzureTokenManager


class TestAzureTokenManager:
    """Test cases for AzureTokenManager class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Reset any cached credentials
        pass
    
    def test_initialization_default(self):
        """Test AzureTokenManager initialization with default settings."""
        manager = AzureTokenManager()
        
        assert manager.client_id is None
        assert manager.use_managed_identity is False
        assert hasattr(manager, 'logger')
        assert hasattr(manager, '_credential')
        assert hasattr(manager, '_cached_tokens')
        assert isinstance(manager._cached_tokens, dict)
    
    def test_initialization_with_client_id(self):
        """Test AzureTokenManager initialization with client ID."""
        client_id = "test-client-id"
        manager = AzureTokenManager(client_id=client_id)
        
        assert manager.client_id == client_id
        assert manager.use_managed_identity is False
    
    def test_initialization_with_managed_identity(self):
        """Test AzureTokenManager initialization with managed identity."""
        manager = AzureTokenManager(use_managed_identity=True)
        
        assert manager.client_id is None
        assert manager.use_managed_identity is True
    
    def test_initialization_with_both_params(self):
        """Test AzureTokenManager initialization with both parameters."""
        client_id = "test-client-id"
        manager = AzureTokenManager(client_id=client_id, use_managed_identity=True)
        
        assert manager.client_id == client_id
        assert manager.use_managed_identity is True
    
    def test_logger_initialization(self):
        """Test that logger is properly initialized."""
        manager = AzureTokenManager()
        
        assert isinstance(manager.logger, logging.Logger)
        assert manager.logger.name == 'osdu_perf.core.auth'
    
    @patch('osdu_perf.core.auth.ManagedIdentityCredential')
    def test_initialize_credential_managed_identity(self, mock_managed_identity):
        """Test _initialize_credential with managed identity."""
        mock_credential = Mock()
        mock_managed_identity.return_value = mock_credential
        
        manager = AzureTokenManager(use_managed_identity=True)
        manager._initialize_credential()
        
        mock_managed_identity.assert_called_once()
        assert manager._credential == mock_credential
    
    @patch('osdu_perf.core.auth.AzureCliCredential')
    def test_initialize_credential_azure_cli_success(self, mock_azure_cli):
        """Test _initialize_credential with Azure CLI success."""
        mock_credential = Mock()
        mock_azure_cli.return_value = mock_credential
        
        manager = AzureTokenManager(use_managed_identity=False)
        manager._initialize_credential()
        
        mock_azure_cli.assert_called_once()
        assert manager._credential == mock_credential
    
    @patch('osdu_perf.core.auth.DefaultAzureCredential')
    @patch('osdu_perf.core.auth.AzureCliCredential')
    def test_initialize_credential_fallback_to_default(self, mock_azure_cli, mock_default):
        """Test _initialize_credential fallback to DefaultAzureCredential."""
        mock_azure_cli.side_effect = Exception("Azure CLI not available")
        mock_default_credential = Mock()
        mock_default.return_value = mock_default_credential
        
        manager = AzureTokenManager(use_managed_identity=False)
        manager._initialize_credential()
        
        mock_azure_cli.assert_called_once()
        mock_default.assert_called_once()
        assert manager._credential == mock_default_credential
    
    def test_cached_tokens_initialization(self):
        """Test that cached tokens dictionary is properly initialized."""
        manager = AzureTokenManager()
        
        assert manager._cached_tokens == {}
        assert isinstance(manager._cached_tokens, dict)
    
    def test_initialization_logging(self):
        """Test that initialization is properly logged."""
        with patch.object(logging.Logger, 'info') as mock_log:
            client_id = "test-client-id"
            manager = AzureTokenManager(client_id=client_id, use_managed_identity=True)
            
            # Should log initialization message
            mock_log.assert_called()
            log_calls = [call.args[0] for call in mock_log.call_args_list]
            init_calls = [call for call in log_calls if "Initialized with Managed Identity credential scope" in call]
            assert len(init_calls) >= 1


class TestAzureTokenManagerCredentialTypes:
    """Test different credential type scenarios."""
    
    @patch('osdu_perf.core.auth.ManagedIdentityCredential')
    def test_managed_identity_credential_creation(self, mock_managed_identity):
        """Test managed identity credential creation."""
        mock_credential = Mock()
        mock_managed_identity.return_value = mock_credential
        
        manager = AzureTokenManager(use_managed_identity=True)
        manager._initialize_credential()
        
        # Verify managed identity credential was created
        mock_managed_identity.assert_called_once_with()
        assert manager._credential is mock_credential
    
    @patch('osdu_perf.core.auth.AzureCliCredential')
    def test_azure_cli_credential_creation(self, mock_azure_cli):
        """Test Azure CLI credential creation."""
        mock_credential = Mock()
        mock_azure_cli.return_value = mock_credential
        
        manager = AzureTokenManager(use_managed_identity=False)
        manager._initialize_credential()
        
        # Verify Azure CLI credential was created
        mock_azure_cli.assert_called_once_with()
        assert manager._credential is mock_credential
    
    @patch('osdu_perf.core.auth.DefaultAzureCredential')
    @patch('osdu_perf.core.auth.AzureCliCredential')
    def test_default_credential_fallback(self, mock_azure_cli, mock_default):
        """Test fallback to DefaultAzureCredential when Azure CLI fails."""
        # Simulate Azure CLI failure
        mock_azure_cli.side_effect = ClientAuthenticationError("CLI not available")
        mock_default_credential = Mock()
        mock_default.return_value = mock_default_credential
        
        manager = AzureTokenManager(use_managed_identity=False)
        manager._initialize_credential()
        
        # Verify fallback occurred
        mock_azure_cli.assert_called_once_with()
        mock_default.assert_called_once_with()
        assert manager._credential is mock_default_credential


class TestAzureTokenManagerEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_multiple_initialization_calls(self):
        """Test that multiple initialization calls work correctly."""
        manager = AzureTokenManager()
        
        # Call _initialize_credential multiple times
        with patch('osdu_perf.core.auth.AzureCliCredential') as mock_azure_cli:
            mock_credential1 = Mock()
            mock_credential2 = Mock()
            mock_azure_cli.side_effect = [mock_credential1, mock_credential2]
            
            manager._initialize_credential()
            first_credential = manager._credential
            
            manager._initialize_credential()
            second_credential = manager._credential
            
            # Both calls should work
            assert first_credential is mock_credential1
            assert second_credential is mock_credential2
    
    def test_client_id_with_different_values(self):
        """Test initialization with various client ID values."""
        # Test with valid GUID
        guid_client_id = "12345678-1234-1234-1234-123456789012"
        manager1 = AzureTokenManager(client_id=guid_client_id)
        assert manager1.client_id == guid_client_id
        
        # Test with custom string
        custom_client_id = "my-custom-app-id"
        manager2 = AzureTokenManager(client_id=custom_client_id)
        assert manager2.client_id == custom_client_id
        
        # Test with empty string
        manager3 = AzureTokenManager(client_id="")
        assert manager3.client_id == ""
    
    def test_cached_tokens_isolation(self):
        """Test that cached tokens are isolated between instances."""
        manager1 = AzureTokenManager()
        manager2 = AzureTokenManager()
        
        # Add token to first manager
        manager1._cached_tokens["scope1"] = Mock()
        
        # Second manager should have empty cache
        assert manager2._cached_tokens == {}
        assert len(manager1._cached_tokens) == 1
    
    @patch('osdu_perf.core.auth.logging.getLogger')
    def test_logger_configuration(self, mock_get_logger):
        """Test that logger is properly configured."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        manager = AzureTokenManager()
        
        mock_get_logger.assert_called_with('osdu_perf.core.auth')
        assert manager.logger is mock_logger