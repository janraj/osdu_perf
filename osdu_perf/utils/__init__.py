# osdu_perf/utils/__init__.py
"""Utilities for OSDU Performance Testing Framework"""

from .environment import detect_environment, get_environment_config

__all__ = [
    "detect_environment",
    "get_environment_config"
]
