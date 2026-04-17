import argparse
from typing import Optional

class ArgParser:
    def __init__(self, logger):
        """
        Initializes the main argument parser.
        """
        self.logger = logger
        self.description =  "OSDU Performance Testing Framework CLI"
        self.parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  osdu_perf init storage              # Initialize tests for storage service
  osdu_perf init search --force       # Force overwrite existing files
  osdu_perf version                   # Show version information
        osdu_perf run local --scenario record_size_1KB
"""
        )
        self.subparsers = self.parser.add_subparsers(
            dest='command', 
            help='Available commands', 
            required=True # Forces the user to provide a command
        )
    
    def _add_osdu_connection_args(self, parser: argparse.ArgumentParser):
        """Adds common OSDU connection arguments to a parser."""
        # OSDU Connection Parameters (Optional - overrides config.yaml values)
        parser.add_argument('--host', help='OSDU host URL (overrides config.yaml)')
        parser.add_argument('--partition', '-p', help='OSDU data partition ID (overrides config.yaml)')
        parser.add_argument('--token', help='Bearer token for OSDU authentication (required)')
        parser.add_argument('--app-id', help='Azure AD Application ID (overrides config.yaml)')
        parser.add_argument('--sku', help='OSDU SKU for metrics collection (overrides config.yaml, default: Standard)')
        parser.add_argument('--version', help='OSDU version for metrics collection (overrides config.yaml, default: 1.0)')

    def _add_split_config_args(self, parser: argparse.ArgumentParser):
        """Adds system config argument with config-folder default."""
        parser.add_argument(
            "--system-config",
            default="config/system_config.yaml",
            help="Path to system_config.yaml file (default: config/system_config.yaml)",
        )

    def _add_implicit_system_config(self, parser: argparse.ArgumentParser):
        """Sets implicit system config path without exposing a CLI flag."""
        parser.set_defaults(system_config="config/system_config.yaml")

    def _add_scenario_arg(self, parser: argparse.ArgumentParser):
        """Adds exactly one scenario name that must exist in test_config.yaml."""
        parser.add_argument(
            "--scenario",
            required=True,
            help="Single scenario name from config/test_config.yaml",
        )

    def _add_config_arg(self, parser: argparse.ArgumentParser):
        """Legacy single-config argument (disabled)."""
        if False:
            parser.add_argument("--config", "-c", required=True, help="Path to config.yaml file (required)")

    def _add_init_command(self):
        """Add 'init' command."""
        init_parser = self.subparsers.add_parser(
            "init", help="Initialize a new performance testing project"
        )
        init_parser.add_argument("service_name", help="Name of the OSDU service to test (e.g., storage, search)")
        init_parser.add_argument("--force", action="store_true", help="Force overwrite existing files")
        init_parser.set_defaults(handler="init")

    def _add_version_command(self):
        """Add 'version' command."""
        version_parser = self.subparsers.add_parser(
            "version", help="Show version information"
        )
        version_parser.set_defaults(handler="version")

    def _add_run_command(self):
        """Add 'run' command and its subcommands (local, azure_load_test)."""
        run_parser = self.subparsers.add_parser("run", help="Run performance tests")

        run_subparsers = run_parser.add_subparsers(
            dest="run_command",
            help="Run command options",
            required=True
        )

        # Run -> local
        self._add_run_local_command(run_subparsers)

        # Run -> azure_load_test
        self._add_run_azure_command(run_subparsers)


    def _add_run_local_command(self, subparsers):
        """Add 'run local' subcommand."""
        local_parser = subparsers.add_parser(
            "local", help="Run local performance tests using bundled locustfiles"
        )

        self._add_implicit_system_config(local_parser)
        self._add_scenario_arg(local_parser)
        self._add_osdu_connection_args(local_parser)

        # Locust Test Parameters (Optional)
        local_parser.add_argument("--users", "-u", type=int, help="Number of concurrent users (default: 100)")
        local_parser.add_argument("--spawn-rate", "-r", type=int, help="User spawn rate per second (default: 5)")
        local_parser.add_argument("--run-time", "-t", help="Test duration (default: 60m)")
        local_parser.add_argument("--engine-instances", "-e", type=int, help="Number of engine instances (default: 10)")

        # Advanced Options
        local_parser.add_argument("--locustfile", "-f", help="Specific locustfile to use (optional)")
        local_parser.add_argument("--list-locustfiles", action="store_true", help="List available bundled locustfiles")
        local_parser.add_argument("--headless", action="store_true", help="Run in headless mode (overrides web UI)")
        local_parser.add_argument("--web-ui", action="store_true", default=True, help="Run with web UI (default)")
        local_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

        local_parser.set_defaults(handler="run_local")

    def _add_run_azure_command(self, subparsers):
        """Add 'run azure_load_test' subcommand."""
        azure_parser = subparsers.add_parser(
            "azure_load_test", help="Run performance tests on Azure Load Testing service"
        )

        self._add_implicit_system_config(azure_parser)
        self._add_scenario_arg(azure_parser)
        self._add_osdu_connection_args(azure_parser)

        # Locust Test Parameters (Optional)
        azure_parser.add_argument("--users", "-u", type=int, help="Number of concurrent users (default: 100)")
        azure_parser.add_argument("--spawn-rate", "-r", type=int, help="User spawn rate per second (default: 5)")
        azure_parser.add_argument("--run-time", "-t", help="Test duration (default: 60m)")
        azure_parser.add_argument("--engine-instances", "-e", type=int, help="Number of engine instances (default: 10)")

        # Azure Configuration
        azure_parser.add_argument("--subscription-id", help="Azure subscription ID (overrides config.yaml)")
        azure_parser.add_argument("--location", help="Azure region (e.g., eastus, westus2) (overrides config.yaml)")

        # Azure Load Test Config
        azure_parser.add_argument("--test-name", help="Test name (auto-generated if not provided)")

        # Advanced Options
        azure_parser.add_argument("--directory", "-d", default=".", help="Directory containing perf_*_test.py files (default: current)")
        azure_parser.add_argument("--force", action="store_true", help="Force overwrite existing tests without prompting")
        azure_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

        azure_parser.set_defaults(handler="run_azure")


    def create_parser(self) -> argparse.ArgumentParser:
        """
        Builds and returns the fully configured argument parser.
        """
        self._add_init_command()
        self._add_version_command()
        self._add_run_command()
        return self.parser