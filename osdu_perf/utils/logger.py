"""
Centralized logging utility for OSDU Performance Testing Framework.
"""
import logging
import sys
from typing import Optional

class OSDULogger:
    """
    Centralized logger for OSDU Performance Testing Framework
    """
    
    _loggers = {}
    _configured = False
    
    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """
        Get a logger instance with the given name.
        
        Args:
            name: Logger name (defaults to 'osdu_perf')
            
        Returns:
            Logger instance
        """
        if name is None:
            name = 'osdu_perf'
            
        if name not in cls._loggers:
            cls._loggers[name] = cls._create_logger(name)
            
        return cls._loggers[name]
    
    @classmethod
    def _create_logger(cls, name: str) -> logging.Logger:
        """Create and configure a logger instance."""
        # Create logger with osdu_perf prefix to make it a child of our root logger
        full_name = f"osdu_perf.{name}" if name != 'osdu_perf' else name
        logger = logging.getLogger(full_name)
        
        if not cls._configured:
            cls._configure_logging()
            cls._configured = True
            
        return logger
    
    @classmethod
    def _configure_logging(cls):
        """Configure the logging system."""
        # Create formatter
        formatter = logging.Formatter(
            '[%(asctime)s %(name)s  %(filename)s:%(lineno)d - %(funcName)s()] %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        root_logger = logging.getLogger('osdu_perf')
        root_logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Add console handler
        root_logger.addHandler(console_handler)
        
        # Allow propagation so child loggers inherit this configuration
        root_logger.propagate = False

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Convenience function to get a logger instance.
    
    Args:
        name: Logger name (defaults to calling module name)
        
    Returns:
        Logger instance
    """
    return OSDULogger.get_logger(name)