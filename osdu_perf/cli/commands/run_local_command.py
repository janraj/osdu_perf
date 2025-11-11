from ..command_base import Command
from ...utils.logger import get_logger

class LocalTestCommand(Command):
    """Command for running local performance tests."""
    def __init__(self, logger):
        self.logger = logger

    def validate_args(self, args) -> bool:
        if not hasattr(args, 'config') or not args.config:
            self.logger.error("❌ Config file is required for local tests")
            return False
        return True
    
    def execute(self, args) -> int:
        try:
            if not self.validate_args(args):
                return 1
                
            from osdu_perf.core.local_test_runner import LocalTestRunner
            runner = LocalTestRunner(logger=self.logger)
            return runner.run_local_tests(args)
        except Exception as e:
            return self.handle_error(e)
        