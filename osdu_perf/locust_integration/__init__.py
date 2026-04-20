# osdu_perf/locust/__init__.py
"""Locust integration for OSDU Performance Testing Framework"""

from .user_base import PerformanceUser
from . import request_interceptor  # noqa: F401  – registers @events.init listener on import

__all__ = [
    "PerformanceUser"
]
