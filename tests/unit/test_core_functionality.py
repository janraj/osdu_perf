"""
Unit tests for core functionality.

Tests basic imports and core module functionality to ensure refactoring didn't break anything.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch


class TestCoreImports:
    """Test core imports work correctly."""

    def test_main_cli_import(self):
        """Test that main CLI function can be imported."""
        from osdu_perf.cli.main import main
        assert callable(main)

    def test_arg_parser_import(self):
        """Test that ArgParser can be imported."""
        from osdu_perf.cli.arg_parser import ArgParser
        assert ArgParser is not None

    def test_command_classes_import(self):
        """Test that command classes can be imported."""
        from osdu_perf.cli.commands.init_command import InitCommand
        from osdu_perf.cli.commands.run_local_command import LocalTestCommand
        from osdu_perf.cli.commands.run_azure_command import AzureLoadTestCommand
        from osdu_perf.cli.commands.version_command import VersionCommand
        
        assert InitCommand is not None
        assert LocalTestCommand is not None
        assert AzureLoadTestCommand is not None
        assert VersionCommand is not None

    def test_local_test_runner_import(self):
        """Test that LocalTestRunner can be imported."""
        from osdu_perf.operations.local_test_runner import LocalTestRunner
        assert LocalTestRunner is not None

    def test_command_factory_import(self):
        """Test that CommandFactory can be imported."""
        from osdu_perf.cli.command_factory import CommandFactory
        assert CommandFactory is not None

    def test_command_invoker_import(self):
        """Test that CommandInvoker can be imported."""
        from osdu_perf.cli.command_invoker import CommandInvoker
        assert CommandInvoker is not None


class TestBasicFunctionality:
    """Test basic functionality works."""

    def test_arg_parser_creation(self):
        """Test ArgParser can be created."""
        from osdu_perf.cli.arg_parser import ArgParser
        
        logger = Mock()
        parser = ArgParser(logger)
        assert parser.logger == logger

    def test_command_factory_creation(self):
        """Test CommandFactory can be created."""
        from osdu_perf.cli.command_factory import CommandFactory
        
        logger = Mock()
        factory = CommandFactory(logger)
        assert factory.logger == logger

    def test_local_test_runner_creation(self):
        """Test LocalTestRunner can be created."""
        from osdu_perf.operations.local_test_operation import LocalTestRunner
        
        logger = Mock()
        # Test LocalTestRunner
        from osdu_perf.operations.local_test_operation import LocalTestRunner
        runner = LocalTestRunner()
        assert runner.logger == logger

    def test_version_command_execution(self):
        """Test version command can be executed."""
        from osdu_perf.cli.commands.version_command import VersionCommand
        
        logger = Mock()
        command = VersionCommand(logger)
        args = Mock()
        
        result = command.execute(args)
        assert result == 0
        logger.info.assert_called()

    def test_package_info_available(self):
        """Test package info is available."""
        import osdu_perf
        assert hasattr(osdu_perf, '__version__')


class TestCLIEntry:
    """Test CLI entry point works."""

    @patch('osdu_perf.cli.main.ArgParser')
    @patch('osdu_perf.cli.main.get_logger')
    def test_main_function_callable(self, mock_get_logger, mock_arg_parser_class):
        """Test main function is callable without errors."""
        from osdu_perf.cli.main import main
        
        # Setup mocks to avoid actual execution
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        mock_parser = Mock()
        mock_parser.parse_args.return_value = Mock(command=None)
        mock_parser.print_help = Mock()
        mock_arg_parser = Mock()
        mock_arg_parser.create_parser.return_value = mock_parser
        mock_arg_parser_class.return_value = mock_arg_parser
        
        # This should not raise any exceptions
        main()
        
        mock_parser.print_help.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])