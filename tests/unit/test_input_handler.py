"""Unit tests for input_handler module."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from osdu_perf.core.input_handler import InputHandler


class TestInputHandler:
    """Test cases for InputHandler."""
    
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
    def mock_token_manager(self):
        """Mock AzureTokenManager."""
        manager = Mock()
        manager.get_access_token.return_value = "test-access-token"
        return manager
    
    @pytest.mark.unit
    @patch('osdu_perf.core.input_handler.AzureTokenManager')
    def test_input_handler_initialization(self, mock_token_manager_class, mock_environment):
        """Test InputHandler initialization."""
        mock_token_manager_instance = Mock()
        mock_token_manager_instance.get_access_token.return_value = "test-token"
        mock_token_manager_class.return_value = mock_token_manager_instance
        
        handler = InputHandler(mock_environment)
        
        # Verify attributes are set correctly
        assert handler.partition == "test-partition"
        assert handler.base_url == "https://test.osdu.com"
        assert handler.app_id == "test-app-id"
        assert handler.header is not None
        
        # Verify token manager was created with correct parameters
        mock_token_manager_class.assert_called_once_with(
            client_id="test-app-id",
            use_managed_identity=False
        )
    
    @pytest.mark.unit
    @patch('osdu_perf.core.input_handler.AzureTokenManager')
    def test_prepare_headers(self, mock_token_manager_class, mock_environment):
        """Test header preparation."""
        mock_token_manager_instance = Mock()
        mock_token_manager_instance.get_access_token.return_value = "test-access-token"
        mock_token_manager_class.return_value = mock_token_manager_instance
        
        handler = InputHandler(mock_environment)
        
        # Verify headers are prepared correctly
        expected_headers = {
            "Content-Type": "application/json",
            "x-data-partition-id": "test-partition",
            "x-correlation-id": "test-app-id",
            "Authorization": "Bearer test-access-token"
        }
        
        assert handler.header == expected_headers
        
        # Verify token was requested with correct scope
        mock_token_manager_instance.get_access_token.assert_called_once_with(
            "https://management.azure.com/.default"
        )
    
    @pytest.mark.unit
    @patch('osdu_perf.core.input_handler.AzureTokenManager')
    def test_prepare_headers_token_failure(self, mock_token_manager_class, mock_environment):
        """Test header preparation when token acquisition fails."""
        mock_token_manager_instance = Mock()
        mock_token_manager_instance.get_access_token.return_value = None
        mock_token_manager_class.return_value = mock_token_manager_instance
        
        handler = InputHandler(mock_environment)
        
        # Headers should still be created but with None token
        expected_headers = {
            "Content-Type": "application/json",
            "x-data-partition-id": "test-partition",
            "x-correlation-id": "test-app-id",
            "Authorization": "Bearer None"
        }
        
        assert handler.header == expected_headers
    
    @pytest.mark.unit
    @patch('osdu_perf.core.input_handler.AzureTokenManager')
    @patch('builtins.print')  # Mock print to verify logging
    def test_initialization_logging(self, mock_print, mock_token_manager_class, mock_environment):
        """Test that initialization logs are created."""
        mock_token_manager_instance = Mock()
        mock_token_manager_instance.get_access_token.return_value = "test-token"
        mock_token_manager_class.return_value = mock_token_manager_instance
        
        InputHandler(mock_environment)
        
        # Verify initialization log was printed
        mock_print.assert_called_once_with(
            "[Input Handler] Host: https://test.osdu.com Partition: test-partition  App ID: test-app-id"
        )
    
    @pytest.mark.unit
    @patch('osdu_perf.core.input_handler.AzureTokenManager')
    def test_different_environment_values(self, mock_token_manager_class):
        """Test with different environment values."""
        mock_token_manager_instance = Mock()
        mock_token_manager_instance.get_access_token.return_value = "different-token"
        mock_token_manager_class.return_value = mock_token_manager_instance
        
        # Create environment with different values
        env = Mock()
        env.host = "https://different.osdu.com"
        env.parsed_options = Mock()
        env.parsed_options.partition = "different-partition"
        env.parsed_options.appid = "different-app-id"
        
        handler = InputHandler(env)
        
        # Verify all values are set correctly
        assert handler.partition == "different-partition"
        assert handler.base_url == "https://different.osdu.com"
        assert handler.app_id == "different-app-id"
        
        expected_headers = {
            "Content-Type": "application/json",
            "x-data-partition-id": "different-partition",
            "x-correlation-id": "different-app-id",
            "Authorization": "Bearer different-token"
        }
        
        assert handler.header == expected_headers
    
    @pytest.mark.unit
    @patch('osdu_perf.core.input_handler.AzureTokenManager')
    def test_token_manager_exception_handling(self, mock_token_manager_class, mock_environment):
        """Test handling of token manager exceptions."""
        mock_token_manager_class.side_effect = Exception("Token manager failed")
        
        # Should raise exception during initialization
        with pytest.raises(Exception, match="Token manager failed"):
            InputHandler(mock_environment)
    
    @pytest.mark.unit
    @patch('osdu_perf.core.input_handler.AzureTokenManager')
    def test_header_immutability(self, mock_token_manager_class, mock_environment):
        """Test that header modifications don't affect the original."""
        mock_token_manager_instance = Mock()
        mock_token_manager_instance.get_access_token.return_value = "test-token"
        mock_token_manager_class.return_value = mock_token_manager_instance
        
        handler = InputHandler(mock_environment)
        original_headers = handler.header.copy()
        
        # Modify the headers
        handler.header["new-header"] = "new-value"
        
        # Original structure should still be intact
        assert "Content-Type" in original_headers
        assert "x-data-partition-id" in original_headers
        assert "x-correlation-id" in original_headers
        assert "Authorization" in original_headers