import argparse
from ..command_base import Command


class InitCommand(Command):
    """Command for initializing new performance testing projects."""

    name = "init"
    help = "Initialize a new performance testing project"
    parent_chain = ()

    def __init__(self, logger):
        self.logger = logger

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("service_name", help="Name of the OSDU service to test (e.g., storage, search)")
        parser.add_argument("--force", action="store_true", help="Force overwrite existing files")
    
    def validate_args(self, args) -> bool:
        if not hasattr(args, 'service_name') or not args.service_name:
            self.logger.error("❌ Service name is required for init command")
            return False
        return True
    
    def execute(self, args) -> int:
        try:
            if not self.validate_args(args):
                return 1
                
            from osdu_perf.operations.init_operation import InitRunner
            init_runner = InitRunner()
            init_runner.init_project(args.service_name, args.force)
            return 0
        except Exception as e:
            return self.handle_error(e)