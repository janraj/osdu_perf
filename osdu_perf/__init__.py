# osdu_perf/__init__.py
"""
OSDU Performance Testing Framework - Core Library
"""

from .core.base_service import BaseService
from .core.service_orchestrator import ServiceOrchestrator
from .core.input_handler import InputHandler
from .core.auth import AzureTokenManager
from .locust.user_base import PerformanceUser
from .utils.environment import detect_environment

__version__ = "1.0.2"
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
