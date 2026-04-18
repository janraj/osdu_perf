"""Push Locust telemetry to Azure Data Explorer (Kusto)."""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass, field
from typing import Any

from azure.kusto.data import DataFormat, KustoClient, KustoConnectionStringBuilder
from azure.kusto.ingest import IngestionProperties, QueuedIngestClient

from ..config import KustoConfig
from ..telemetry import get_logger
from .schemas import (
    EXCEPTIONS_TABLE,
    METRICS_TABLE,
    SUMMARY_TABLE,
    TIMESERIES_TABLE,
    build_provisioning_script,
)

_LOGGER = get_logger("kusto")


@dataclass
class TelemetryPayload:
    """Rows ready for ingestion into the four V2 tables."""

    metrics: list[dict[str, Any]] = field(default_factory=list)
    exceptions: list[dict[str, Any]] = field(default_factory=list)
    summary: list[dict[str, Any]] = field(default_factory=list)
    timeseries: list[dict[str, Any]] = field(default_factory=list)


class KustoIngestor:
    """Thin wrapper around :class:`QueuedIngestClient`.

    Chooses managed-identity auth when running inside Azure Load Testing
    and Azure CLI auth for local runs. Writes MULTIJSON so dynamic
    columns (``Labels``, ``StatusCodes``) are ingested as native values.
    """

    def __init__(self, config: KustoConfig, *, use_managed_identity: bool) -> None:
        if not config.is_configured:
            raise ValueError("Kusto config is incomplete (need cluster_uri + database)")
        self._config = config
        self._use_managed_identity = use_managed_identity
        self._client: QueuedIngestClient | None = None

    def ingest(self, payload: TelemetryPayload) -> None:
        """Ingest every non-empty table in ``payload``."""
        client = self._client or self._build_client()
        self._client = client

        self._ingest_table(client, payload.metrics, METRICS_TABLE, "metrics")
        self._ingest_table(client, payload.exceptions, EXCEPTIONS_TABLE, "exceptions")
        self._ingest_table(client, payload.summary, SUMMARY_TABLE, "summary")
        self._ingest_table(client, payload.timeseries, TIMESERIES_TABLE, "timeseries")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_client(self) -> QueuedIngestClient:
        endpoint = self._config.ingest_uri or self._config.cluster_uri
        assert endpoint is not None
        if self._use_managed_identity:
            if os.getenv("AZURE_FEDERATED_TOKEN_FILE"):
                from azure.identity import WorkloadIdentityCredential

                _LOGGER.info("Kusto auth: workload identity (%s)", endpoint)
                kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
                    endpoint, WorkloadIdentityCredential()
                )
            else:
                _LOGGER.info("Kusto auth: managed identity (%s)", endpoint)
                kcsb = (
                    KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
                        endpoint
                    )
                )
        else:
            _LOGGER.info("Kusto auth: az cli (%s)", endpoint)
            kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(endpoint)
        return QueuedIngestClient(kcsb)

    def _ingest_table(
        self,
        client: QueuedIngestClient,
        rows: list[dict[str, Any]],
        table: str,
        label: str,
    ) -> None:
        if not rows:
            return
        props = IngestionProperties(
            database=self._config.database,
            table=table,
            data_format=DataFormat.MULTIJSON,
        )
        payload = "\n".join(json.dumps(row, default=str) for row in rows)
        client.ingest_from_stream(io.StringIO(payload), props)
        _LOGGER.info("Ingested %d %s row(s) into %s", len(rows), label, table)


def provision_tables(config: KustoConfig, *, use_managed_identity: bool = False) -> list[str]:
    """Run every DDL statement from :func:`build_provisioning_script`.

    Uses the *query* endpoint (cluster URI, not ingest URI) because
    ``.create-merge table`` and friends are control commands, not
    ingestion calls. Returns the list of commands executed so callers
    can log or print them.

    Requires the caller to have **Database Admin** (or Table Admin on
    each table) rights. ``use_managed_identity=True`` is only useful
    when running this inside an Azure-hosted environment with an MI
    that has those rights; for local/one-time setup Azure CLI auth is
    almost always the right choice.
    """
    if not config.is_configured:
        raise ValueError("Kusto config is incomplete (need cluster_uri + database)")
    endpoint = config.cluster_uri
    assert endpoint is not None
    if use_managed_identity:
        kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
            endpoint
        )
    else:
        kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(endpoint)

    commands = build_provisioning_script()
    client = KustoClient(kcsb)
    try:
        for cmd in commands:
            client.execute_mgmt(config.database, cmd)
            _LOGGER.info("Kusto DDL ok: %s", _summarise_command(cmd))
    finally:
        client.close()
    return commands


def _summarise_command(cmd: str) -> str:
    """Return the first ~80 chars of a DDL command (before the column list)."""
    head = cmd.split("(", 1)[0].strip()
    return head[:80]


__all__ = ["KustoIngestor", "TelemetryPayload", "provision_tables"]
