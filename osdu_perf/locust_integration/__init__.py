# osdu_perf/locust_integration/__init__.py
"""Locust integration for OSDU Performance Testing Framework"""

from .user import PerformanceUser
from . import middleware  # noqa: F401  – registers @events.init listener on import

__all__ = [
    "PerformanceUser"
]
