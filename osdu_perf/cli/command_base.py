from abc import ABC, abstractmethod

class Command(ABC):
    """Abstract base class for all CLI commands."""
    
    def __init__(self, logger):
        self.logger = logger
    
    @abstractmethod
    def execute(self, args) -> int:
        """Execute the command and return exit code."""
        pass
    
    @abstractmethod
    def validate_args(self, args) -> bool:
        """Validate command arguments."""
        pass
    
    def handle_error(self, error: Exception) -> int:
        """Common error handling for all commands."""
        self.logger.error(f"❌ Error: {error}")
        return 1