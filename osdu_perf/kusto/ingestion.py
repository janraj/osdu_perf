"""Push Locust telemetry to Azure Data Explorer (Kusto)."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from typing import Any

from azure.kusto.data import DataFormat, KustoConnectionStringBuilder
from azure.kusto.ingest import IngestionProperties, QueuedIngestClient

from ..config import KustoConfig
from ..telemetry import get_logger
from .schemas import EXCEPTIONS_TABLE, METRICS_TABLE, SUMMARY_TABLE

_LOGGER = get_logger("kusto")


@dataclass
class TelemetryPayload:
    """Rows ready for ingestion into the three V2 tables."""

    metrics: list[dict[str, Any]] = field(default_factory=list)
    exceptions: list[dict[str, Any]] = field(default_factory=list)
    summary: list[dict[str, Any]] = field(default_factory=list)


class KustoIngestor:
    """Thin wrapper around :class:`QueuedIngestClient`.

    Chooses managed-identity auth when running inside Azure Load Testing
    and Azure CLI auth for local runs. Writes MULTIJSON so the ``Metadata``
    column is ingested as a native dynamic value.
    """

    def __init__(self, config: KustoConfig, *, use_managed_identity: bool) -> None:
        if not config.is_configured:
            raise ValueError("Kusto config is incomplete (need cluster_uri + database)")
        self._config = config
        self._use_managed_identity = use_managed_identity
        self._client: QueuedIngestClient | None = None

    def ingest(self, payload: TelemetryPayload) -> None:
        """Ingest metrics, exceptions and summary rows into their V2 tables."""
        client = self._client or self._build_client()
        self._client = client

        self._ingest_table(client, payload.metrics, METRICS_TABLE, "metrics")
        self._ingest_table(client, payload.exceptions, EXCEPTIONS_TABLE, "exceptions")
        self._ingest_table(client, payload.summary, SUMMARY_TABLE, "summary")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_client(self) -> QueuedIngestClient:
        endpoint = self._config.ingest_uri or self._config.cluster_uri
        assert endpoint is not None
        if self._use_managed_identity:
            _LOGGER.info("Kusto auth: managed identity (%s)", endpoint)
            kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
                endpoint
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


__all__ = ["KustoIngestor", "TelemetryPayload"]
