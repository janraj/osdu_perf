"""
Unit tests for the ArgParser class.

Tests the argument parsing functionality and helper methods.
"""

import pytest
from unittest.mock import Mock
from argparse import ArgumentParser

from osdu_perf.cli.arg_parser import ArgParser


class TestArgParserClass:
    """Test cases for the ArgParser class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = Mock()
        self.arg_parser = ArgParser(self.logger)

    def test_initialization(self):
        """Test ArgParser initialization."""
        assert self.arg_parser.logger == self.logger
        assert self.arg_parser.description == "OSDU Performance Testing Framework CLI"
        assert self.arg_parser.parser is not None
        assert self.arg_parser.subparsers is not None

    def test_create_parser_returns_argument_parser(self):
        """Test that create_parser returns an ArgumentParser."""
        parser = self.arg_parser.create_parser()
        assert isinstance(parser, ArgumentParser)

    def test_parser_description(self):
        """Test parser has correct description."""
        parser = self.arg_parser.create_parser()
        assert parser.description == "OSDU Performance Testing Framework CLI"

    def test_subcommands_exist(self):
        """Test that required subcommands exist by trying to parse them."""
        parser = self.arg_parser.create_parser()
        
        # Test that the main commands work without error
        try:
            parser.parse_args(['init', 'storage'])
            init_works = True
        except SystemExit:
            init_works = False
        
        try:
            parser.parse_args(['version'])
            version_works = True
        except SystemExit:
            version_works = False
            
        try:
            parser.parse_args([
                'run', 'local',
                '--scenario', 'record_size_1KB',
                '--token', 'test'
            ])
            local_works = True
        except SystemExit:
            local_works = False
            
        assert init_works, "init command should be available"
        assert version_works, "version command should be available"
        assert local_works, "run local command should be available"

    def test_init_command_parser(self):
        """Test init command argument parsing."""
        parser = self.arg_parser.create_parser()
        
        # Test with valid arguments
        args = parser.parse_args(['init', 'storage'])
        assert args.command == 'init'
        assert args.service_name == 'storage'
        assert args.force is False
        
        # Test with force flag
        args = parser.parse_args(['init', 'storage', '--force'])
        assert args.force is True

    def test_version_command_parser(self):
        """Test version command argument parsing."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args(['version'])
        assert args.command == 'version'

    def test_run_local_command_parser(self):
        """Test run local command argument parsing."""
        parser = self.arg_parser.create_parser()
        
        # Test with required arguments
        args = parser.parse_args([
            'run', 'local',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token'
        ])
        
        assert args.command == 'run'
        assert args.run_command == 'local'
        assert args.system_config == 'config/system_config.yaml'
        assert args.scenario == 'record_size_1KB'
        assert args.token == 'test-token'
        assert args.headless is False  # Default value

    def test_run_local_command_with_all_options(self):
        """Test run local command with all optional arguments."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'local',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token',
            '--host', 'https://test.com',
            '--partition', 'test-partition',
            '--users', '100',
            '--spawn-rate', '10',
            '--run-time', '5m',
            '--headless'
        ])
        
        assert args.system_config == 'config/system_config.yaml'
        assert args.scenario == 'record_size_1KB'
        assert args.token == 'test-token'
        assert args.host == 'https://test.com'
        assert args.partition == 'test-partition'
        assert args.users == 100
        assert args.spawn_rate == 10
        assert args.run_time == '5m'
        assert args.headless is True

    def test_run_azure_command_parser(self):
        """Test run azure_load_test command argument parsing."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'azure_load_test',
            '--system-config', 'system_config.yaml',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token',
            '--subscription-id', 'test-sub-id'
        ])
        
        assert args.command == 'run'
        assert args.run_command == 'azure_load_test'
        assert args.system_config == 'system_config.yaml'
        assert args.scenario == 'record_size_1KB'
        assert args.token == 'test-token'
        assert args.subscription_id == 'test-sub-id'
        assert args.force is False  # Default value

    def test_run_azure_command_with_all_options(self):
        """Test run azure_load_test command with all optional arguments."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'azure_load_test',
            '--system-config', 'system_config.yaml',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token',
            '--subscription-id', 'test-sub-id',
            '--host', 'https://test.com',
            '--partition', 'test-partition',
            '--resource-group', 'test-rg',
            '--location', 'eastus',
            '--force'
        ])
        
        assert args.system_config == 'system_config.yaml'
        assert args.scenario == 'record_size_1KB'
        assert args.token == 'test-token'
        assert args.subscription_id == 'test-sub-id'
        assert args.host == 'https://test.com'
        assert args.partition == 'test-partition'
        assert args.resource_group == 'test-rg'
        assert args.location == 'eastus'
        assert args.force is True

    def test_osdu_connection_args_helper_in_local(self):
        """Test that OSDU connection args helper is used in local command."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'local',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token',
            '--host', 'https://example.com',
            '--partition', 'example-partition'
        ])
        
        # These arguments should be available due to _add_osdu_connection_args
        assert hasattr(args, 'host')
        assert hasattr(args, 'partition')
        assert args.host == 'https://example.com'
        assert args.partition == 'example-partition'

    def test_osdu_connection_args_helper_in_azure(self):
        """Test that OSDU connection args helper is used in azure command."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'azure_load_test',
            '--system-config', 'system_config.yaml',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token',
            '--subscription-id', 'test-sub',
            '--host', 'https://example.com',
            '--partition', 'example-partition'
        ])
        
        # These arguments should be available due to _add_osdu_connection_args
        assert hasattr(args, 'host')
        assert hasattr(args, 'partition')
        assert args.host == 'https://example.com'
        assert args.partition == 'example-partition'

    def test_config_arg_helper_in_local(self):
        """Test that scenario arg helper is used in local command."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'local',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token'
        ])
        
        assert hasattr(args, 'system_config')
        assert hasattr(args, 'scenario')
        assert args.system_config == 'config/system_config.yaml'
        assert args.scenario == 'record_size_1KB'

    def test_config_arg_helper_in_azure(self):
        """Test that scenario arg helper is used in azure command."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'azure_load_test',
            '--system-config', 'custom-system-config.yaml',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token',
            '--subscription-id', 'test-sub'
        ])
        
        assert hasattr(args, 'system_config')
        assert hasattr(args, 'scenario')
        assert args.system_config == 'custom-system-config.yaml'
        assert args.scenario == 'record_size_1KB'

    def test_invalid_command_parsing(self):
        """Test parsing invalid commands."""
        parser = self.arg_parser.create_parser()
        
        # Test invalid main command
        with pytest.raises(SystemExit):
            parser.parse_args(['invalid'])
        
        # Test invalid run subcommand
        with pytest.raises(SystemExit):
            parser.parse_args(['run', 'invalid'])

    def test_argument_types(self):
        """Test that arguments have correct types."""
        parser = self.arg_parser.create_parser()
        
        args = parser.parse_args([
            'run', 'local',
            '--scenario', 'record_size_1KB',
            '--token', 'test-token',
            '--users', '50',
            '--spawn-rate', '5'
        ])
        
        # Test integer type conversion
        assert isinstance(args.users, int)
        assert isinstance(args.spawn_rate, int)
        assert args.users == 50
        assert args.spawn_rate == 5

    def test_multiple_scenarios_blocked_in_local(self):
        """Test parser blocks multiple scenario values for local command."""
        parser = self.arg_parser.create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([
                'run', 'local',
                '--scenario', 'record_size_1KB', 'record_size_100KB',
                '--token', 'test-token'
            ])

    def test_multiple_scenarios_blocked_in_azure(self):
        """Test parser blocks multiple scenario values for azure command."""
        parser = self.arg_parser.create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([
                'run', 'azure_load_test',
                '--system-config', 'system_config.yaml',
                '--scenario', 'record_size_1KB', 'record_size_100KB',
                '--token', 'test-token',
                '--subscription-id', 'test-sub-id'
            ])


if __name__ == '__main__':
    pytest.main([__file__])