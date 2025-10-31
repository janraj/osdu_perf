from .command_factory import CommandFactory

class CommandInvoker:
    """Invoker that executes commands."""
    
    def __init__(self, logger):
        self.logger = logger
        self.factory = CommandFactory(logger)

    
    def execute_command(self, command_name: str, args) -> int:
        """Execute a command by name."""
        self.logger.info(f"Command Invoker is called with command: {command_name}")
        command = self.factory.create_command(command_name)
        
        if not command:
            self.logger.error(f"❌ Unknown command: {command_name} Available commands: {', '.join(self.factory.get_available_commands())}")
            return 1
        self.logger.info(f"Executing command: {command_name}")
        return command.execute(args)