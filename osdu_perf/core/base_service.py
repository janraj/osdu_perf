from abc import ABC, abstractmethod

class BaseService(ABC):
    """Base class for all service classes that need HTTP client access"""
    
    def __init__(self, client=None):
        """
        Initialize with HTTP client.
        
        Args:
            client: HTTP client (typically Locust's self.client or requests)
        """
        self.client = client
    
    @abstractmethod
    def execute(self, headers=None, partition=None, host=None):
        """
        Abstract method that should be implemented by subclasses.
        This method should call all the service-specific tasks.
        """
        raise NotImplementedError("Subclasses must implement execute() method")
