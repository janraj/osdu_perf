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


    @abstractmethod
    def provide_explicit_token(self):
        """
        Abstract method for providing an explicit token for service execution.
        """
        raise NotImplementedError("Subclasses must implement provide_explicit_token() method")

    @abstractmethod
    def prehook(self):
        """
        Abstract method for pre-hook tasks before service execution.
        """
        raise NotImplementedError("Subclasses must implement prehook() method")

    @abstractmethod
    def posthook(self):
        """
        Abstract method for post-hook tasks after service execution.
        """
        raise NotImplementedError("Subclasses must implement posthook() method")