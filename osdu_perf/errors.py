"""Typed exception hierarchy for ``osdu_perf``.

All library-raised exceptions inherit from :class:`OsduPerfError` so CLI
callers can present friendly messages without leaking tracebacks. Internal
errors that would indicate a bug (not user error) are allowed to propagate
as plain ``Exception`` subclasses.
"""

from __future__ import annotations


class OsduPerfError(Exception):
    """Base class for all user-facing errors raised by ``osdu_perf``."""


class ConfigError(OsduPerfError):
    """Raised when user configuration is missing, malformed, or invalid."""


class ScenarioNotFoundError(ConfigError):
    """Raised when a requested scenario is not defined in ``test_config.yaml``."""


class AuthError(OsduPerfError):
    """Raised when Azure authentication fails or no credential is available."""


class AzureResourceError(OsduPerfError):
    """Raised when an Azure resource is missing or cannot be provisioned."""


class ScaffoldError(OsduPerfError):
    """Raised by ``osdu_perf init`` when scaffolding cannot be completed."""


__all__ = [
    "OsduPerfError",
    "ConfigError",
    "ScenarioNotFoundError",
    "AuthError",
    "AzureResourceError",
    "ScaffoldError",
]
