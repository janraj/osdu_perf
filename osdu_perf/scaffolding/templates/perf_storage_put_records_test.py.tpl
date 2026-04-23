"""Performance test for OSDU Storage ``PUT /records``.

Hammers ``PUT /api/storage/v2/records`` with a randomised
``master-data--Well`` payload on every call. Each request creates /
upserts a record **without** an explicit ``id`` field so the server
assigns one. The legaltag is created **once per worker process**
during ``prehook``; all subsequent users reuse it.

Every PUT payload randomises ``FacilityID`` and the first
``AliasName`` (WELL_NAME alias) with a 8-character alphanumeric string
so that each request produces a unique record body.

All HTTP calls go through Locust so they show up in
``LocustMetricsV2`` / ``LocustExceptionsV2``.

Environment knobs (all optional):

* ``STORAGE_LEGALTAG_NAME``      — legaltag to create / reference.
  Defaults to ``{partition}-public-usa-check-1``.
* ``STORAGE_RECORD_KIND``        — kind for the upserted records.
  Defaults to ``osdu:wks:master-data--Well:1.0.0``.
"""

from __future__ import annotations

import os
import random
import string
import threading

import osdu_perf

from osdu_perf import BaseService


_GUARD_NAME = "_storage_put_records_legaltag_setup_v1"
if not hasattr(osdu_perf, _GUARD_NAME):
    setattr(osdu_perf, _GUARD_NAME, {"done": False, "lock": threading.Lock()})
_GUARD: dict = getattr(osdu_perf, _GUARD_NAME)

_RAND_CHARS = string.ascii_uppercase + string.digits


def _rand_id(length: int = 8) -> str:
    return "".join(random.choices(_RAND_CHARS, k=length))


class ${CLASS_NAME}(BaseService):
    """PUT /api/storage/v2/records — bombard with randomised Well payloads."""

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

        with _GUARD["lock"]:
            if _GUARD["done"]:
                return
            self._ensure_legaltag(headers)
            _GUARD["done"] = True

    def execute(self, headers=None, partition=None, host=None) -> None:
        record = self._build_record()
        self.client.put(
            "/api/storage/v2/records",
            json=[record],
            name="${SAMPLE_NAME}",
            headers=self._with_correlation(headers, "put-records"),
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

    def _build_record(self) -> dict:
        partition = self._partition
        facility_id = _rand_id()
        return {
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
                        "AliasName": facility_id,
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
                "FacilityID": facility_id,
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
        merged["correlation-id"] = self.new_correlation_id(action)
        if self._partition and "data-partition-id" not in {k.lower() for k in merged}:
            merged["data-partition-id"] = self._partition
        return merged
