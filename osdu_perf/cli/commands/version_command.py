from pathlib import Path
from ..command_base import Command
from ...utils.logger import get_logger
from ... import __version__


class VersionCommand(Command):
    """Command for displaying version information."""
    
    def __init__(self, logger):
        self.logger = logger

    def validate_args(self, args) -> bool:
        return True  # No validation needed for version command
    
    def execute(self, args) -> int:
        try:
            self.version_command()  # Existing function
            return 0
        except Exception as e:
            return self.handle_error(e)
        
    def version_command(self):
        """Show version information"""
        self.logger.info(f"OSDU Performance Testing Framework v{__version__}")
        self.logger.info(f"Location: {Path(__file__).parent}")
        self.logger.info("Dependencies:")

        try:
            import locust
            self.logger.info(f"  • locust: {locust.__version__}")
        except ImportError:
            self.logger.info("  • locust: not installed")

        try:
            import azure.identity
            self.logger.info(f"  • azure-identity: {azure.identity.__version__}")
        except (ImportError, AttributeError):
            self.logger.info("  • azure-identity: not installed")