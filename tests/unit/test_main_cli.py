"""
Test cases for main CLI entry point.
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from osdu_perf.cli.main import main


class TestMain:
    """Test cases for main CLI function."""
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_successful_execution(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test successful main execution."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'version'
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        mock_invoker = Mock()
        mock_invoker.execute_command.return_value = 0
        mock_invoker_class.return_value = mock_invoker
        
        main()
        
        # Verify environment variables are set
        assert os.environ['GEVENT_SUPPORT'] == 'False'
        assert os.environ['NO_GEVENT_MONKEY_PATCH'] == '1'
        
        # Verify logger creation
        mock_get_logger.assert_called_once_with('CLI')
        
        # Verify parser creation and usage
        mock_arg_parser_class.assert_called_once_with(mock_logger)
        mock_arg_parser.create_parser.assert_called_once()
        mock_parser.parse_args.assert_called_once()
        
        # Verify command execution
        mock_invoker_class.assert_called_once_with(mock_logger)
        mock_invoker.execute_command.assert_called_once_with('version', mock_args)
        
        # Verify no sys.exit called on success
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_no_command_prints_help(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test main when no command is provided."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = None  # No command provided
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        result = main()
        
        # Verify help is printed
        mock_parser.print_help.assert_called_once()
        
        # Verify command invoker is not created when no command
        mock_invoker_class.assert_not_called()
        
        # Verify no sys.exit called
        mock_sys_exit.assert_not_called()
        
        # Function should return None
        assert result is None
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_run_command_with_subcommand(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test main with run command and subcommand."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'run'
        mock_args.run_command = 'local'
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        mock_invoker = Mock()
        mock_invoker.execute_command.return_value = 0
        mock_invoker_class.return_value = mock_invoker
        
        main()
        
        # Verify command execution with subcommand
        mock_invoker.execute_command.assert_called_once_with('local', mock_args)
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_run_command_azure_subcommand(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test main with run command and azure subcommand."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'run'
        mock_args.run_command = 'azure_load_test'
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        mock_invoker = Mock()
        mock_invoker.execute_command.return_value = 0
        mock_invoker_class.return_value = mock_invoker
        
        main()
        
        # Verify command execution with azure subcommand
        mock_invoker.execute_command.assert_called_once_with('azure_load_test', mock_args)
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_init_command(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test main with init command."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'init'
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        mock_invoker = Mock()
        mock_invoker.execute_command.return_value = 0
        mock_invoker_class.return_value = mock_invoker
        
        main()
        
        # Verify command execution with init
        mock_invoker.execute_command.assert_called_once_with('init', mock_args)
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_command_failure_exits(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test main exits when command fails."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'version'
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        mock_invoker = Mock()
        mock_invoker.execute_command.return_value = 1  # Command failed
        mock_invoker_class.return_value = mock_invoker
        
        main()
        
        # Verify sys.exit called with failure code
        mock_sys_exit.assert_called_once_with(1)
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_command_failure_different_exit_codes(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test main handles different exit codes."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'init'
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        mock_invoker = Mock()
        mock_invoker.execute_command.return_value = 2  # Different failure code
        mock_invoker_class.return_value = mock_invoker
        
        main()
        
        # Verify sys.exit called with the specific failure code
        mock_sys_exit.assert_called_once_with(2)
    
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_sets_environment_variables(self, mock_get_logger):
        """Test that main sets required environment variables."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Clear environment variables first
        if 'GEVENT_SUPPORT' in os.environ:
            del os.environ['GEVENT_SUPPORT']
        if 'NO_GEVENT_MONKEY_PATCH' in os.environ:
            del os.environ['NO_GEVENT_MONKEY_PATCH']
        
        with patch('osdu_perf.cli.main.ArgParser') as mock_arg_parser_class:
            mock_parser = Mock()
            mock_args = Mock()
            mock_args.command = None  # This will cause early return
            mock_parser.parse_args.return_value = mock_args
            
            mock_arg_parser = Mock()
            mock_arg_parser.create_parser.return_value = mock_parser
            mock_arg_parser_class.return_value = mock_arg_parser
            
            main()
        
        # Verify environment variables are set
        assert os.environ['GEVENT_SUPPORT'] == 'False'
        assert os.environ['NO_GEVENT_MONKEY_PATCH'] == '1'
        
        # Verify logger debug call about gevent
        mock_logger.debug.assert_called_once_with("disable gevent monkey patch: 1")
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandInvoker')
    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_zero_exit_code_no_exit(self, mock_get_logger, mock_arg_parser_class, mock_invoker_class, mock_sys_exit):
        """Test that zero exit code doesn't call sys.exit."""
        # Setup mocks
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'version'
        mock_parser.parse_args.return_value = mock_args
        
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        mock_invoker = Mock()
        mock_invoker.execute_command.return_value = 0  # Success
        mock_invoker_class.return_value = mock_invoker
        
        main()
        
        # Verify sys.exit is NOT called for success
        mock_sys_exit.assert_not_called()


class TestMainAsScript:
    """Test cases for running main as a script."""
    
    def test_main_function_exists_and_callable(self):
        """Test that main function exists and is callable."""
        from osdu_perf.cli.main import main
        
        # Verify the main function exists and is callable
        assert callable(main)
        
        # Test that it can be called (with proper mocking to avoid side effects)
        with patch('osdu_perf.cli.main.sys.exit'):
            with patch('osdu_perf.cli.main.ArgParser') as mock_arg_parser_class:
                mock_parser = Mock()
                mock_args = Mock()
                mock_args.command = None  # This will cause early return (help)
                mock_parser.parse_args.return_value = mock_args
                
                mock_arg_parser = Mock()
                mock_arg_parser.create_parser.return_value = mock_parser
                mock_arg_parser_class.return_value = mock_arg_parser
                
                # This should not raise an exception
                main()