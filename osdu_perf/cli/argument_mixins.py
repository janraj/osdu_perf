import argparse


class OsduConnectionMixin:
    """Adds --host, --partition, --token, --app-id, --performance-tier, --version."""

    @staticmethod
    def add_osdu_args(parser: argparse.ArgumentParser):
        parser.add_argument('--host', help='OSDU host URL (overrides config.yaml)')
        parser.add_argument('--partition', '-p', help='OSDU data partition ID (overrides config.yaml)')
        parser.add_argument('--token', help='Bearer token for OSDU authentication (optional, falls back to Azure CLI credential)')
        parser.add_argument('--app-id', help='Azure AD Application ID (overrides config.yaml)')
        parser.add_argument('--performance-tier', dest='performance_tier',
                            help='Test profile/performance tier from test_config.yaml (overrides system_config.yaml performance_tier)')
        parser.add_argument('--version', help='Test version identifier for test names and run tracking (can be any number/string, e.g., 20260417)')


class LocustParamsMixin:
    """Adds --users, --spawn-rate, --run-time, --engine-instances."""

    @staticmethod
    def add_locust_args(parser: argparse.ArgumentParser):
        parser.add_argument('--users', '-u', type=int, help='Number of concurrent users (default: 100)')
        parser.add_argument('--spawn-rate', '-r', type=int, help='User spawn rate per second (default: 5)')
        parser.add_argument('--run-time', '-t', help='Test duration (default: 60m)')
        parser.add_argument('--engine-instances', '-e', type=int, help='Number of engine instances (default: 10)')


class ScenarioMixin:
    """Adds --scenario (required)."""

    @staticmethod
    def add_scenario_arg(parser: argparse.ArgumentParser):
        parser.add_argument('--scenario', required=True, help='Single scenario name from config/test_config.yaml')


class SystemConfigMixin:
    """Sets implicit system_config default without exposing a CLI flag."""

    @staticmethod
    def add_system_config_default(parser: argparse.ArgumentParser):
        parser.set_defaults(system_config='config/system_config.yaml')


class VerboseMixin:
    """Adds --verbose / -v."""

    @staticmethod
    def add_verbose_arg(parser: argparse.ArgumentParser):
        parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
