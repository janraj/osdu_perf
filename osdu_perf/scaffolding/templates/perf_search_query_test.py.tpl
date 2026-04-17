"""Performance test for OSDU Search Query using random record ids.

Issues ``POST /api/search/v2/query`` with a ``File.Generic`` record id
whose numeric suffix is randomised on every call, to avoid cache hits.

Environment knobs (all optional):

* ``SEARCH_QUERY_KIND``                — kind to search within. Defaults
  to ``<partition>:wks:dataset--File.Generic:1.0.0``.
* ``SEARCH_QUERY_RECORD_ID_PREFIX``    — id prefix before the random
  suffix. Defaults to ``<partition>:dataset--File.Generic:``.
* ``SEARCH_QUERY_RECORD_ID_MIN``       — inclusive lower bound of the
  random suffix (default ``1000``).
* ``SEARCH_QUERY_RECORD_ID_MAX``       — inclusive upper bound of the
  random suffix (default ``2000``).
"""

from __future__ import annotations

import os
import random

from osdu_perf import BaseService


class ${CLASS_NAME}(BaseService):
    """POST /api/search/v2/query with a randomised record id per call."""

    def provide_explicit_token(self) -> str:
        return ""

    def prehook(self, headers=None, partition=None, host=None) -> None:
        self._kind = os.getenv(
            "SEARCH_QUERY_KIND",
            f"{partition}:wks:dataset--File.Generic:1.0.0",
        )
        self._id_prefix = os.getenv(
            "SEARCH_QUERY_RECORD_ID_PREFIX",
            f"{partition}:dataset--File.Generic:",
        )
        self._min_suffix = int(os.getenv("SEARCH_QUERY_RECORD_ID_MIN", "1000"))
        self._max_suffix = int(os.getenv("SEARCH_QUERY_RECORD_ID_MAX", "2000"))
        if self._min_suffix > self._max_suffix:
            self._min_suffix, self._max_suffix = self._max_suffix, self._min_suffix

    def execute(self, headers=None, partition=None, host=None) -> None:
        suffix = random.randint(self._min_suffix, self._max_suffix)
        record_id = f"{self._id_prefix}{suffix}"
        payload = {
            "kind": self._kind,
            "query": f'id:("{record_id}")',
        }
        self.client.post(
            "${SAMPLE_ENDPOINT}",
            json=payload,
            name="${SAMPLE_NAME}",
            headers=headers,
        )

    def posthook(self, headers=None, partition=None, host=None) -> None:
        pass
