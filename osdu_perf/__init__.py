"""OSDU performance testing framework."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._version import __version__
from .config import AppConfig, load_config

# The testing layer imports locust, which monkey-patches stdlib (subprocess,
# socket, etc.) via gevent. That breaks the CLI on Windows (CreateProcess
# fails). Re-export those names lazily so importing osdu_perf for CLI/runner
# code paths does not pull in locust.
if TYPE_CHECKING:
    from .testing import BaseService, PerformanceUser, ServiceRegistry  # noqa: F401

__all__ = [
    "__version__",
    "AppConfig",
    "BaseService",
    "PerformanceUser",
    "ServiceRegistry",
    "load_config",
]


def __getattr__(name: str) -> Any:
    if name in {"BaseService", "PerformanceUser", "ServiceRegistry"}:
        from . import testing

        return getattr(testing, name)
    raise AttributeError(f"module 'osdu_perf' has no attribute '{name}'")
