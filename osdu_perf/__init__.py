"""
OSDU Performance Testing Framework - Core Library
"""

from .operations.base_service import BaseService
from .operations.service_orchestrator import ServiceOrchestrator
from .operations.input_handler import InputHandler
from .operations.auth import AzureTokenManager
from .utils.environment import detect_environment
from .operations.init_operation import InitRunner
from .locust_integration.user_base import PerformanceUser


__version__ = "1.0.40"
__author__ = "Janraj CJ"
__email__ = "janrajcj@microsoft.com"

__all__ = [
    "InitRunner",
    "BaseService",
    "ServiceOrchestrator", 
    "InputHandler",
    "AzureTokenManager",
    "PerformanceUser",
    "detect_environment"
]
