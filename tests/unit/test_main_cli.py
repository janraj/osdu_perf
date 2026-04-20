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
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_successful_execution(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test successful main execution."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'version'
        mock_parser.parse_args.return_value = mock_args
        
        mock_command = Mock()
        mock_command.execute.return_value = 0
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry.resolve.return_value = mock_command
        mock_registry_class.return_value = mock_registry
        
        main()
        
        assert os.environ['GEVENT_SUPPORT'] == 'False'
        assert os.environ['NO_GEVENT_MONKEY_PATCH'] == '1'
        mock_get_logger.assert_called_once_with('CLI')
        mock_registry.build_parser.assert_called_once()
        mock_parser.parse_args.assert_called_once()
        mock_registry.resolve.assert_called_once_with(mock_args)
        mock_command.execute.assert_called_once_with(mock_args)
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_no_command_prints_help(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test main when no command is provided."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = None
        mock_parser.parse_args.return_value = mock_args
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry_class.return_value = mock_registry
        
        result = main()
        
        mock_parser.print_help.assert_called_once()
        mock_registry.resolve.assert_not_called()
        mock_sys_exit.assert_not_called()
        assert result is None
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_run_command_with_subcommand(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test main with run command and subcommand."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'run'
        mock_parser.parse_args.return_value = mock_args
        
        mock_command = Mock()
        mock_command.execute.return_value = 0
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry.resolve.return_value = mock_command
        mock_registry_class.return_value = mock_registry
        
        main()
        
        mock_registry.resolve.assert_called_once_with(mock_args)
        mock_command.execute.assert_called_once_with(mock_args)
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_run_command_azure_subcommand(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test main with run command and azure subcommand."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'run'
        mock_parser.parse_args.return_value = mock_args
        
        mock_command = Mock()
        mock_command.execute.return_value = 0
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry.resolve.return_value = mock_command
        mock_registry_class.return_value = mock_registry
        
        main()
        
        mock_registry.resolve.assert_called_once_with(mock_args)
        mock_command.execute.assert_called_once_with(mock_args)
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_init_command(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test main with init command."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'init'
        mock_parser.parse_args.return_value = mock_args
        
        mock_command = Mock()
        mock_command.execute.return_value = 0
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry.resolve.return_value = mock_command
        mock_registry_class.return_value = mock_registry
        
        main()
        
        mock_registry.resolve.assert_called_once_with(mock_args)
        mock_command.execute.assert_called_once_with(mock_args)
        mock_sys_exit.assert_not_called()
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_command_failure_exits(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test main exits when command fails."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'version'
        mock_parser.parse_args.return_value = mock_args
        
        mock_command = Mock()
        mock_command.execute.return_value = 1
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry.resolve.return_value = mock_command
        mock_registry_class.return_value = mock_registry
        
        main()
        
        mock_sys_exit.assert_called_once_with(1)
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_command_failure_different_exit_codes(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test main handles different exit codes."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'init'
        mock_parser.parse_args.return_value = mock_args
        
        mock_command = Mock()
        mock_command.execute.return_value = 2
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry.resolve.return_value = mock_command
        mock_registry_class.return_value = mock_registry
        
        main()
        
        mock_sys_exit.assert_called_once_with(2)
    
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_sets_environment_variables(self, mock_get_logger):
        """Test that main sets required environment variables."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        if 'GEVENT_SUPPORT' in os.environ:
            del os.environ['GEVENT_SUPPORT']
        if 'NO_GEVENT_MONKEY_PATCH' in os.environ:
            del os.environ['NO_GEVENT_MONKEY_PATCH']
        
        with patch('osdu_perf.cli.main.CommandRegistry') as mock_registry_class:
            mock_parser = Mock()
            mock_args = Mock()
            mock_args.command = None
            mock_parser.parse_args.return_value = mock_args
            
            mock_registry = Mock()
            mock_registry.build_parser.return_value = mock_parser
            mock_registry_class.return_value = mock_registry
            
            main()
        
        assert os.environ['GEVENT_SUPPORT'] == 'False'
        assert os.environ['NO_GEVENT_MONKEY_PATCH'] == '1'
        mock_logger.debug.assert_called_once_with("disable gevent monkey patch: 1")
    
    @patch('osdu_perf.cli.main.sys.exit')
    @patch('osdu_perf.cli.main.CommandRegistry')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_zero_exit_code_no_exit(self, mock_get_logger, mock_registry_class, mock_sys_exit):
        """Test that zero exit code doesn't call sys.exit."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.command = 'version'
        mock_parser.parse_args.return_value = mock_args
        
        mock_command = Mock()
        mock_command.execute.return_value = 0
        
        mock_registry = Mock()
        mock_registry.build_parser.return_value = mock_parser
        mock_registry.resolve.return_value = mock_command
        mock_registry_class.return_value = mock_registry
        
        main()
        
        mock_sys_exit.assert_not_called()


class TestMainAsScript:
    """Test cases for running main as a script."""
    
    def test_main_function_exists_and_callable(self):
        """Test that main function exists and is callable."""
        from osdu_perf.cli.main import main
        
        assert callable(main)
        
        with patch('osdu_perf.cli.main.sys.exit'):
            with patch('osdu_perf.cli.main.CommandRegistry') as mock_registry_class:
                mock_parser = Mock()
                mock_args = Mock()
                mock_args.command = None
                mock_parser.parse_args.return_value = mock_args
                
                mock_registry = Mock()
                mock_registry.build_parser.return_value = mock_parser
                mock_registry_class.return_value = mock_registry
                
                main()