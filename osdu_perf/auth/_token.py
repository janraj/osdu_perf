"""Azure access-token acquisition.

A single :class:`TokenProvider` chooses the right credential for the
environment (Azure Load Testing managed identity, Azure CLI locally, or a
pre-supplied bearer token) and caches tokens per scope.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass

from azure.identity import AzureCliCredential, ManagedIdentityCredential

from ..errors import AuthError
from ..telemetry import get_logger


@dataclass(frozen=True)
class TokenContext:
    """Input for :meth:`TokenProvider.get_token`."""

    app_id: str


class TokenProvider:
    """Fetch Azure access tokens using the most appropriate credential.

    Resolution:

    * If ``ADME_BEARER_TOKEN`` is set or an explicit ``token`` is supplied,
      return it as-is.
    * Else, if running inside Azure Load Testing (detected via env vars),
      use :class:`ManagedIdentityCredential`.
    * Else, shell out to ``az account get-access-token`` so the resulting
      token's ``aud`` matches the bare OSDU app id (the Python Azure CLI
      credential appends ``/.default`` which OSDU rejects).
    """

    def __init__(self, *, explicit_token: str | None = None) -> None:
        self._logger = get_logger("auth")
        self._explicit_token = explicit_token or os.getenv("ADME_BEARER_TOKEN")
        self._cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_token(self, app_id: str) -> str:
        """Return a bearer token for ``app_id``. Raises :class:`AuthError`."""
        if self._explicit_token:
            return self._explicit_token

        cached = self._cache.get(app_id)
        if cached:
            return cached

        if _is_managed_identity_env():
            token = self._managed_identity_token(app_id)
        else:
            token = self._azure_cli_token(app_id)

        self._cache[app_id] = token
        return token

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------
    def _managed_identity_token(self, app_id: str) -> str:
        scope = f"api://{app_id}/.default"
        self._logger.info("Acquiring token via Managed Identity (scope=%s)", scope)
        try:
            credential = ManagedIdentityCredential(client_id=app_id)
            result = credential.get_token(scope)
        except Exception as exc:
            raise AuthError(f"Managed Identity token acquisition failed: {exc}") from exc
        return result.token

    def _azure_cli_token(self, app_id: str) -> str:
        self._logger.info("Acquiring token via Azure CLI (resource=%s)", app_id)
        for cmd in ("az", "az.exe", "az.cmd"):
            try:
                proc = subprocess.run(
                    [cmd, "account", "get-access-token", "--resource", app_id],
                    capture_output=True,
                    text=True,
                    check=False,
                    shell=True,
                )
            except FileNotFoundError:
                continue
            if proc.returncode == 0:
                try:
                    return json.loads(proc.stdout)["accessToken"]
                except (json.JSONDecodeError, KeyError) as exc:
                    raise AuthError(
                        f"Unexpected output from 'az account get-access-token': {exc}"
                    ) from exc
            self._logger.debug("%s failed (%s): %s", cmd, proc.returncode, proc.stderr.strip())

        # Fallback to the SDK credential if the CLI wasn't on PATH.
        try:
            credential = AzureCliCredential()
            result = credential.get_token(f"api://{app_id}/.default")
            return result.token
        except Exception as exc:
            raise AuthError(
                "Unable to acquire token. Ensure Azure CLI is installed and "
                "you have run 'az login', or set ADME_BEARER_TOKEN."
            ) from exc


def _is_managed_identity_env() -> bool:
    """True when we're running inside Azure Load Testing (or similar)."""
    return any(
        os.getenv(flag)
        for flag in (
            "AZURE_LOAD_TEST",
            "LOCUST_HOST",
            "LOCUST_USERS",
            "LOCUST_RUN_TIME",
            "LOCUST_SPAWN_RATE",
        )
    )


__all__ = ["TokenProvider", "TokenContext"]
