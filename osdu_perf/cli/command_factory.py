from typing import Optional
from .command_base import Command
from .commands.init_command import InitCommand
from .commands.run_local_command import LocalTestCommand
from .commands.run_azure_command import AzureLoadTestCommand  
from .commands.version_command import VersionCommand

class CommandFactory:
    """Factory for creating command instances."""
    
    def __init__(self, logger):
        self.logger = logger
        self._commands = {
            'init': InitCommand,
            'local': LocalTestCommand,
            'azure_load_test': AzureLoadTestCommand,
            'version': VersionCommand
        }
        self.logger.info(f"Available commands: {list(self._commands.keys())}")
    
    def create_command(self, command_name: str) -> Optional[Command]:
        """Create a command instance by name."""
        self.logger.info(f"Creating command: {command_name}")
        command_class = self._commands.get(command_name)
        if command_class:
            return command_class(self.logger)
        self.logger.error(f"Unknown command class for: {command_name}")
        return None
    
    def get_available_commands(self) -> list:
        """Get list of available command names."""
        self.logger.info("Fetching available commands")
        return list(self._commands.keys())