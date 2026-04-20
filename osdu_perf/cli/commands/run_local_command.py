import argparse
from ..command_base import Command
from ..argument_mixins import (
    OsduConnectionMixin,
    LocustParamsMixin,
    ScenarioMixin,
    SystemConfigMixin,
    VerboseMixin,
)
from ...utils.logger import get_logger


class LocalTestCommand(
    Command, OsduConnectionMixin, LocustParamsMixin,
    ScenarioMixin, SystemConfigMixin, VerboseMixin,
):
    """Command for running local performance tests."""

    name = "local"
    help = "Run local performance tests using bundled locustfiles"
    parent_chain = ("run",)

    def __init__(self, logger):
        self.logger = logger

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        # Shared argument groups
        self.add_system_config_default(parser)
        self.add_scenario_arg(parser)
        self.add_osdu_args(parser)
        self.add_locust_args(parser)
        self.add_verbose_arg(parser)

        # Local-only arguments
        parser.add_argument('--locustfile', '-f', help='Specific locustfile to use (optional)')
        parser.add_argument('--list-locustfiles', action='store_true', help='List available bundled locustfiles')
        parser.add_argument('--headless', action='store_true', help='Run in headless mode (no web UI)')

    def validate_args(self, args) -> bool:
        if not hasattr(args, 'scenario') or not args.scenario:
            self.logger.error("❌ Exactly one --scenario value is required for local tests")
            return False
        return True
    
    def execute(self, args) -> int:
        try:
            if not self.validate_args(args):
                return 1
                
            from osdu_perf.operations.local_test_operation import LocalTestRunner
            runner = LocalTestRunner(logger=self.logger)
            return runner.run_local_tests(args)
        except Exception as e:
            return self.handle_error(e)
        