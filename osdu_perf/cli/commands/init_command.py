from ..command_base import Command

class InitCommand(Command):
    """Command for initializing new performance testing projects."""

    def __init__(self, logger):
        self.logger = logger
    
    def validate_args(self, args) -> bool:
        if not hasattr(args, 'service_name') or not args.service_name:
            self.logger.error("❌ Service name is required for init command")
            return False
        return True
    
    def execute(self, args) -> int:
        try:
            if not self.validate_args(args):
                return 1
                
            from osdu_perf.core.init_runner import InitRunner
            init_runner = InitRunner()
            init_runner.init_project(args.service_name, args.force)
            return 0
        except Exception as e:
            return self.handle_error(e)