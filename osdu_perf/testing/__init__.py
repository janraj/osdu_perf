"""Locust integration for ``osdu_perf``.

Public API:

* :class:`PerformanceUser` — base class for your Locust user
* :class:`BaseService` — contract for each service's performance tasks
* :class:`ServiceRegistry` — auto-discovers ``perf_*_test.py`` modules
"""

from .base_service import BaseService
from .services import ServiceRegistry
from .user import PerformanceUser

__all__ = ["BaseService", "PerformanceUser", "ServiceRegistry"]
