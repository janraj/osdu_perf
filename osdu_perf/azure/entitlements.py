"""OSDU entitlement provisioning for an Azure Load Test resource's identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ..errors import AzureResourceError
from ..telemetry import get_logger

_LOGGER = get_logger("azure.entitlements")


@dataclass(frozen=True)
class EntitlementResult:
    success: bool
    message: str
    group_results: list[dict[str, Any]]


class EntitlementProvisioner:
    """Grants the ALT identity the OSDU groups it needs.

    Steps:

    1. Resolve the ALT identity's ``appId`` from its principal (object) id
       via Microsoft Graph.
    2. Add that appId to the standard OSDU user groups
       (``users@...``, ``users.datalake.editors@...``,
       ``users.datalake.admins@...``).
    """

    _STANDARD_GROUPS = (
        "users@{partition}.dataservices.energy",
        "users.datalake.editors@{partition}.dataservices.energy",
        "users.datalake.admins@{partition}.dataservices.energy",
    )

    def __init__(self, credential: Any, principal_id: str) -> None:
        self._credential = credential
        self._principal_id = principal_id

    def provision(
        self,
        *,
        host: str,
        partition: str,
        osdu_token: str,
    ) -> EntitlementResult:
        app_id = self._resolve_app_id()
        headers = {
            "data-partition-id": partition,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {osdu_token}",
        }
        base = host.rstrip("/")

        results: list[dict[str, Any]] = []
        overall = True
        for group_template in self._STANDARD_GROUPS:
            group = group_template.format(partition=partition)
            outcome = self._add_member(base, group, app_id, headers)
            results.append(outcome)
            if not outcome["success"]:
                overall = False

        message = _summary(results)
        _LOGGER.info("Entitlement provisioning finished: %s", message)
        return EntitlementResult(success=overall, message=message, group_results=results)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _resolve_app_id(self) -> str:
        _LOGGER.info("Resolving appId for principal %s via Microsoft Graph", self._principal_id)
        token = self._credential.get_token("https://graph.microsoft.com/").token
        url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{self._principal_id}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if resp.status_code != 200:
            raise AzureResourceError(
                f"Microsoft Graph returned {resp.status_code} resolving "
                f"principal '{self._principal_id}': {resp.text}"
            )
        payload = resp.json()
        app_id = payload.get("appId")
        if not app_id:
            raise AzureResourceError(
                f"No appId found for principal '{self._principal_id}'"
            )
        _LOGGER.info("Resolved appId %s for principal %s", app_id, self._principal_id)
        return app_id

    def _add_member(
        self,
        base: str,
        group: str,
        app_id: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        url = f"{base}/api/entitlements/v2/groups/{group}/members"
        payload = {"email": app_id, "role": "MEMBER"}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.RequestException as exc:
            _LOGGER.error("Error adding %s to group %s: %s", app_id, group, exc)
            return {"group": group, "success": False, "conflict": False, "message": str(exc)}

        is_success = 200 <= resp.status_code < 300
        is_conflict = resp.status_code == 409
        if is_conflict:
            message = f"already a member of {group}"
        elif is_success:
            message = f"added to {group}"
        else:
            message = f"failed ({resp.status_code}): {resp.text}"
        return {
            "group": group,
            "success": is_success or is_conflict,
            "conflict": is_conflict,
            "message": message,
        }


def _summary(results: list[dict[str, Any]]) -> str:
    ok = [r for r in results if r["success"] and not r["conflict"]]
    existing = [r for r in results if r["conflict"]]
    failed = [r for r in results if not r["success"]]
    parts: list[str] = []
    if ok:
        parts.append(f"{len(ok)} added")
    if existing:
        parts.append(f"{len(existing)} already existed")
    if failed:
        parts.append(f"{len(failed)} failed")
    return ", ".join(parts) or "no groups processed"


__all__ = ["EntitlementProvisioner", "EntitlementResult"]
