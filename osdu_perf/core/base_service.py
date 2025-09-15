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
    def provide_explicit_token(self) -> str:
        """
        Abstract method for providing an explicit token for service execution.
        
        Returns:
            str: Authentication token for API requests
        """
        raise NotImplementedError("Subclasses must implement provide_explicit_token() method")

    @abstractmethod
    def prehook(self, headers=None, partition=None, host=None):
        """
        Abstract method for pre-hook tasks before service execution.
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            host: Host URL for the service
        """
        raise NotImplementedError("Subclasses must implement prehook() method")

    @abstractmethod
    def posthook(self, headers=None, partition=None, host=None):
        """
        Abstract method for post-hook tasks after service execution.
        
        Args:
            headers: HTTP headers including authentication
            partition: Data partition ID  
            host: Host URL for the service
        """
        raise NotImplementedError("Subclasses must implement posthook() method")