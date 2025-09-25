"""
OSDU Performance Testing Framework - Core Library
"""

from .core.base_service import BaseService
from .core.service_orchestrator import ServiceOrchestrator
from .core.input_handler import InputHandler
from .core.auth import AzureTokenManager
from .utils.environment import detect_environment

# Conditional import to avoid Locust monkey patching during azure_load_test
import sys
if not any('azure_load_test' in str(arg) for arg in sys.argv):
    try:
        from .locust.user_base import PerformanceUser
    except ImportError:
        # Locust not available, skip import
        pass

__version__ = "1.0.14"
__author__ = "Janraj CJ"
__email__ = "janrajcj@microsoft.com"

__all__ = [
    "BaseService",
    "ServiceOrchestrator", 
    "InputHandler",
    "AzureTokenManager",
    "PerformanceUser",
    "detect_environment"
]
