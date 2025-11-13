"""
Test cases for local test runner command.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from osdu_perf.cli.commands.run_local_command import LocalTestCommand


class TestLocalTestCommand:
    """Test cases for LocalTestCommand."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.logger_mock = Mock()
        self.local_command = LocalTestCommand(self.logger_mock)
    
    def test_initialization(self):
        """Test LocalTestCommand initialization."""
        assert self.local_command.logger == self.logger_mock
    
    def test_validate_args_success(self):
        """Test successful args validation."""
        args = Mock()
        args.config = "config.yaml"
        args.token = "test_token"
        
        result = self.local_command.validate_args(args)
        assert result is True
    
    def test_validate_args_missing_config(self):
        """Test validation failure when config is missing."""
        args = Mock()
        args.config = None
        args.token = "test_token"
        
        result = self.local_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_missing_token(self):
        """Test validation failure when token is missing."""
        args = Mock()
        args.config = "config.yaml"
        args.token = None
        
        result = self.local_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_empty_config(self):
        """Test validation failure when config is empty."""
        args = Mock()
        args.config = ""
        args.token = "test_token"
        
        result = self.local_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_empty_token(self):
        """Test validation failure when token is empty."""
        args = Mock()
        args.config = "config.yaml"
        args.token = ""
        
        result = self.local_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_no_config_attribute(self):
        """Test validation failure when args has no config attribute."""
        args = Mock(spec=['token'])  # Mock with limited attributes
        args.token = "test_token"
        
        result = self.local_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_no_token_attribute(self):
        """Test validation failure when args has no token attribute."""
        args = Mock(spec=['config'])  # Mock with limited attributes
        args.config = "config.yaml"
        
        result = self.local_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    @patch('osdu_perf.operations.local_test_runner.LocalTestRunner')
    def test_execute_success(self, mock_runner_class):
        """Test successful execution of local test command."""
        args = Mock()
        args.config = "config.yaml"
        args.token = "test_token"
        
        mock_runner = Mock()
        mock_runner.run_local_tests.return_value = 0
        mock_runner_class.return_value = mock_runner
        
        result = self.local_command.execute(args)
        
        mock_runner_class.assert_called_once_with(logger=self.logger_mock)
        mock_runner.run_local_tests.assert_called_once_with(args)
        assert result == 0
    
    def test_execute_validation_failure(self):
        """Test execute when validation fails."""
        args = Mock()
        args.config = None
        args.token = "test_token"
        
        result = self.local_command.execute(args)
        assert result == 1
    
    @patch('osdu_perf.operations.local_test_runner.LocalTestRunner')
    def test_execute_handles_exception(self, mock_runner_class):
        """Test that execute handles exceptions properly."""
        args = Mock()
        args.config = "config.yaml"
        args.token = "test_token"
        
        mock_runner_class.side_effect = Exception("test error")
        
        with patch.object(self.local_command, 'handle_error', return_value=1) as mock_handle:
            result = self.local_command.execute(args)
            mock_handle.assert_called_once()
            assert result == 1
    
    @patch('osdu_perf.operations.local_test_runner.LocalTestRunner')
    def test_execute_runner_failure(self, mock_runner_class):
        """Test execute when runner returns failure code."""
        args = Mock()
        args.config = "config.yaml"
        args.token = "test_token"
        
        mock_runner = Mock()
        mock_runner.run_local_tests.return_value = 2  # Failure code
        mock_runner_class.return_value = mock_runner
        
        result = self.local_command.execute(args)
        
        mock_runner_class.assert_called_once_with(logger=self.logger_mock)
        mock_runner.run_local_tests.assert_called_once_with(args)
        assert result == 2
    
    def test_validate_args_both_missing(self):
        """Test validation failure when both required args are missing."""
        args = Mock()
        args.config = None
        args.token = None
        
        result = self.local_command.validate_args(args)
        assert result is False
        self.logger_mock.error.assert_called_once()
    
    def test_validate_args_with_valid_values(self):
        """Test validation success with various valid values."""
        args = Mock()
        
        # Test with valid config and token
        args.config = "test_config.yaml"
        args.token = "valid_token_123"
        assert self.local_command.validate_args(args) is True
        
        # Test with different valid values
        args.config = "/absolute/path/config.json"
        args.token = "another_valid_token"
        assert self.local_command.validate_args(args) is True