"""Performance test for OSDU Storage ``GET /records/{id}``.

Hammers ``GET /api/storage/v2/records/{id}`` against records created
**once per Locust worker process** during ``prehook``. With N
distributed workers the legaltag + record setup runs N times total,
no matter how many users you ramp to. Both setup calls are
idempotent on the server side:

* ``POST /api/legal/v1/legaltags`` creates the legaltag named
  ``${LEGALTAG_NAME_DEFAULT}`` (substituting ``{partition}`` with the
  configured data-partition-id). A 409 from the legal service is
  treated as success — the tag already exists.
* ``PUT /api/storage/v2/records`` upserts ``STORAGE_RECORD_COUNT``
  ``master-data--Well`` records with ids
  ``{partition}:master-data--Well:perf{1..N}``. PUT is idempotent on
  ``id`` so re-runs simply overwrite the same payload.

``execute`` then issues ``GET /api/storage/v2/records/<id>`` picking a
random record id from the seeded set. All HTTP calls go through Locust
so they show up in ``LocustMetricsV2`` / ``LocustExceptionsV2``.

Environment knobs (all optional):

* ``STORAGE_LEGALTAG_NAME``      — legaltag to create / reference.
  Defaults to ``{partition}-public-usa-check-1``.
* ``STORAGE_RECORD_KIND``        — kind for the seeded records.
  Defaults to ``osdu:wks:master-data--Well:1.0.0``.
* ``STORAGE_RECORD_ID_PREFIX``   — id prefix before the numeric suffix.
  Defaults to ``{partition}:master-data--Well:perf``.
* ``STORAGE_RECORD_COUNT``       — number of records to seed and pick
  from on every GET (default ``1``).
"""

from __future__ import annotations

import os
import random
import threading
import uuid

import osdu_perf

from osdu_perf import BaseService


# Process-stable one-shot guard. We stash on the ``osdu_perf`` module
# object (loaded exactly once per Python process) instead of relying on
# class attributes, so that even if this test module is re-executed
# mid-run (e.g. by a future ``ServiceRegistry`` that disables module
# caching), the setup still fires only once per worker process.
_GUARD_NAME = "_storage_get_record_by_id_setup_v1"
if not hasattr(osdu_perf, _GUARD_NAME):
    setattr(osdu_perf, _GUARD_NAME, {"done": False, "lock": threading.Lock()})
_GUARD: dict = getattr(osdu_perf, _GUARD_NAME)


class ${CLASS_NAME}(BaseService):
    """GET /api/storage/v2/records/{id} after one-shot legaltag + record setup."""

    # Human-friendly label for dashboards. Rows ingested into
    # LocustMetricsV2 / LocustExceptionsV2 use this as the ``Service`` column.
    service_name = "storage"

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def provide_explicit_token(self) -> str:
        return ""

    def prehook(self, headers=None, partition=None, host=None) -> None:
        self._partition = partition or os.getenv("PARTITION", "")
        self._legaltag = os.getenv(
            "STORAGE_LEGALTAG_NAME",
            f"{self._partition}-public-usa-check-1",
        )
        self._kind = os.getenv(
            "STORAGE_RECORD_KIND",
            "osdu:wks:master-data--Well:1.0.0",
        )
        self._id_prefix = os.getenv(
            "STORAGE_RECORD_ID_PREFIX",
            f"{self._partition}:master-data--Well:perf",
        )
        self._record_count = max(1, int(os.getenv("STORAGE_RECORD_COUNT", "1")))
        self._record_ids = [
            f"{self._id_prefix}{i}" for i in range(1, self._record_count + 1)
        ]

        # Run setup exactly once per worker process. Subsequent users
        # spawning in the same process see ``done=True`` and skip the
        # HTTP calls entirely.
        with _GUARD["lock"]:
            if _GUARD["done"]:
                return
            self._ensure_legaltag(headers)
            self._ensure_records(headers)
            _GUARD["done"] = True

    def execute(self, headers=None, partition=None, host=None) -> None:
        record_id = random.choice(self._record_ids)
        self.client.get(
            f"/api/storage/v2/records/{record_id}",
            name="${SAMPLE_NAME}",
            headers=self._with_correlation(headers, "get-record"),
        )

    def posthook(self, headers=None, partition=None, host=None) -> None:
        pass

    # ------------------------------------------------------------------
    # Setup helpers (idempotent; called once per worker process)
    # ------------------------------------------------------------------
    def _ensure_legaltag(self, headers) -> None:
        body = {
            "name": self._legaltag,
            "description": "load test tag",
            "properties": {
                "contractId": "A1234",
                "countryOfOrigin": ["US"],
                "dataType": "Public Domain Data",
                "expirationDate": "2099-01-25",
                "exportClassification": "EAR99",
                "originator": "MyCompany",
                "personalData": "No Personal Data",
                "securityClassification": "Public",
            },
        }
        # Mark these calls so they don't pollute the GET stats. The
        # ``catch_response=True`` + ``response.success()`` pattern lets
        # us treat 409 (already exists) as a success on the legaltag.
        with self.client.post(
            "/api/legal/v1/legaltags",
            json=body,
            name="${SAMPLE_NAME}__setup_legaltag",
            headers=self._with_correlation(headers, "create-legaltag"),
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201, 409):
                response.success()
            else:
                response.failure(
                    f"create legaltag failed: {response.status_code} {response.text[:300]}"
                )

    def _ensure_records(self, headers) -> None:
        records = [self._build_record(rid) for rid in self._record_ids]
        with self.client.put(
            "/api/storage/v2/records",
            json=records,
            name="${SAMPLE_NAME}__setup_records",
            headers=self._with_correlation(headers, "create-records"),
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            else:
                response.failure(
                    f"upsert records failed: {response.status_code} {response.text[:300]}"
                )

    def _build_record(self, record_id: str) -> dict:
        partition = self._partition
        return {
            "id": record_id,
            "kind": self._kind,
            "acl": {
                "owners": [
                    f"data.default.owners@{partition}.dataservices.energy"
                ],
                "viewers": [
                    f"data.default.viewers@{partition}.dataservices.energy"
                ],
            },
            "data": {
                "Source": "TNO",
                "NameAliases": [
                    {
                        "AliasName": "ACA-11",
                        "AliasNameTypeID": "opendes:reference-data--AliasNameType:WELL_NAME:",
                    },
                    {
                        "AliasName": "1000",
                        "AliasNameTypeID": "opendes:reference-data--AliasNameType:UWI:",
                    },
                ],
                "GeoContexts": [
                    {
                        "GeoPoliticalEntityID": "opendes:master-data--GeoPoliticalEntity:Netherlands:",
                        "GeoTypeID": "opendes:reference-data--GeoPoliticalEntityType:Country:",
                    },
                    {
                        "GeoPoliticalEntityID": "opendes:master-data--GeoPoliticalEntity:Limburg:",
                        "GeoTypeID": "opendes:reference-data--GeoPoliticalEntityType:State%2FProvinceID:",
                    },
                    {
                        "GeoPoliticalEntityID": "opendes:master-data--GeoPoliticalEntity:L:",
                        "GeoTypeID": "opendes:reference-data--GeoPoliticalEntityType:Quadrant:",
                    },
                ],
                "SpatialLocation": {
                    "Wgs84Coordinates": {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [5.98136045, 51.43503877],
                                },
                                "properties": {},
                            }
                        ],
                    }
                },
                "FacilityID": "ACA-11",
                "FacilityTypeID": "opendes:reference-data--FacilityType:WELL_NAME:",
                "FacilityOperators": [
                    {
                        "FacilityOperatorOrganisationID": "opendes:master-data--Organisation:ROVD:"
                    }
                ],
                "OperatingEnvironmentID": "opendes:reference-data--OperatingEnvironment:ON:",
                "FacilityStates": [
                    {
                        "FacilityStateTypeID": "opendes:reference-data--FacilityStateType:Abandoned:"
                    }
                ],
                "FacilityEvents": [
                    {
                        "FacilityEventTypeID": "opendes:reference-data--FacilityEventType:SPUD:",
                        "EffectiveDateTime": "1909-04-05T00:00:00",
                    },
                    {
                        "FacilityEventTypeID": "opendes:reference-data--FacilityEventType:DRILLING%20FINISH:",
                        "EffectiveDateTime": "1910-01-19T00:00:00",
                    },
                ],
                "DefaultVerticalMeasurementID": "Rotary Table",
                "VerticalMeasurements": [
                    {
                        "VerticalMeasurementID": "Rotary Table",
                        "VerticalMeasurement": 29.3,
                        "VerticalMeasurementTypeID": "opendes:reference-data--VerticalMeasurementType:Rotary%20Table:",
                        "VerticalMeasurementPathID": "opendes:reference-data--VerticalMeasurementPath:Elevation:",
                        "VerticalMeasurementUnitOfMeasureID": "opendes:reference-data--UnitOfMeasure:M:",
                        "VerticalCRSID": "opendes:reference-data--CoordinateReferenceSystem:NAP:",
                    }
                ],
            },
            "legal": {
                "legaltags": [self._legaltag],
                "otherRelevantDataCountries": ["US"],
            },
        }

    # ------------------------------------------------------------------
    def _with_correlation(self, headers, action: str) -> dict:
        merged = dict(headers or {})
        # <testRunId>-<action>-<short unique> so server-side logs can be
        # filtered per test run.  Falls back to action-only if test_run_id
        # hasn't been set (e.g. standalone Locust without osdu_perf).
        uid = uuid.uuid4().hex[:12]
        if self.test_run_id:
            merged["correlation-id"] = f"{self.test_run_id}-{action}-{uid}"
        else:
            merged["correlation-id"] = f"{action}-{uid}"
        if self._partition and "data-partition-id" not in {k.lower() for k in merged}:
            merged["data-partition-id"] = self._partition
        return merged
