# osdu_perf/locust_integration/middleware.py
"""
Request middleware for Locust HttpSession.

Ensures every outgoing request carries a complete set of headers:
    - Authorization: Bearer <token>
    - data-partition-id: <partition>
    - Content-Type: application/json
    - correlation-id: <test_run_id>, <test_name_prefix>-<uuid>

Headers already present on the request are NOT overridden.
Only missing headers are filled from InputHandler / environment.

The correlation-id is always refreshed to include a per-request uuid.
Its uuid length is dynamically sized (8–32 hex chars) to fill the
remaining space up to the 128-char cap.

Activation is automatic – importing this module registers a
``@events.init`` listener that patches ``HttpSession.request`` once.
No test-code changes are required.
"""

import os
import uuid
import logging
from datetime import datetime
from locust import events
from locust.clients import HttpSession

logger = logging.getLogger(__name__)

_MAX_HEADER_LEN = 128
_original_request = None


def _get_test_name_prefix():
    """Get test_name_prefix from PerformanceUser's InputHandler (lazy import to avoid circular)."""
    from .user import PerformanceUser
    ih = PerformanceUser._input_handler_instance
    if ih:
        return ih.get_test_name_prefix()
    return "osdu_perf_test"


def _get_input_handler():
    """Get InputHandler instance from PerformanceUser (lazy import to avoid circular)."""
    from .user import PerformanceUser
    return PerformanceUser._input_handler_instance


def _ensure_authorization(headers):
    """Fill Authorization header if missing. Re-reads ADME_BEARER_TOKEN for freshness."""
    if "Authorization" in headers:
        return
    token = os.getenv("ADME_BEARER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        return
    ih = _get_input_handler()
    if ih and ih.header and "Authorization" in ih.header:
        headers["Authorization"] = ih.header["Authorization"]


def _ensure_partition(headers):
    """Fill data-partition-id header if missing."""
    if "data-partition-id" in headers:
        return
    ih = _get_input_handler()
    if ih and ih.partition:
        headers["data-partition-id"] = ih.partition


def _ensure_content_type(headers):
    """Fill Content-Type header if missing."""
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"


def _intercepted_request(self, method, url, **kwargs):
    """Wrap every outgoing request to ensure full headers are present."""
    headers = kwargs.get("headers")
    if headers is None:
        headers = {}
        kwargs["headers"] = headers

    # --- Fill missing standard headers ---
    _ensure_authorization(headers)
    _ensure_partition(headers)
    _ensure_content_type(headers)

    # --- Per-request correlation-id ---

    test_run_id = headers.get("correlation-id", "")
    prefix = _get_test_name_prefix()

    # The headers dict is shared across requests, so correlation-id may
    # already contain appended per-request IDs from a previous call.
    # Always extract only the first value (the original test-run ID).
    if "," in test_run_id:
        test_run_id = test_run_id.split(",", 1)[0].strip()

    # If no correlation-id was set, build the test-run ID from InputHandler
    if not test_run_id:
        test_run_id_env = os.getenv("TEST_RUN_ID_NAME") or os.getenv("TEST_RUN_ID")
        test_run_id = test_run_id_env or f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Dynamically size the uuid to fill remaining space up to 128 chars.
    # Layout: "<test_run_id>, <prefix>-<uuid>"
    #   fixed overhead = len(test_run_id) + 2 (", ") + len(prefix) + 1 ("-")
    fixed_len = len(test_run_id) + 2 + len(prefix) + 1
    uid_len = max(8, min(32, _MAX_HEADER_LEN - fixed_len))  # 8..32 hex chars
    request_uid = uuid.uuid4().hex[:uid_len]

    per_request_id = f"{prefix}-{request_uid}"
    combined = f"{test_run_id}, {per_request_id}"

    # Safety: if test_run_id is very long, trim prefix to stay within cap
    if len(combined) > _MAX_HEADER_LEN:
        remaining = _MAX_HEADER_LEN - len(test_run_id) - 2 - 1 - 8
        per_request_id = f"{prefix[:max(1, remaining)]}-{uuid.uuid4().hex[:8]}"
        combined = f"{test_run_id}, {per_request_id}"

    headers["correlation-id"] = combined
    return _original_request(self, method, url, **kwargs)


@events.init.add_listener
def _install_middleware(environment, **kwargs):
    """Patch HttpSession.request once when Locust initialises."""
    global _original_request
    if _original_request is None:
        _original_request = HttpSession.request
        HttpSession.request = _intercepted_request
        logger.info(
            "[osdu_perf] Request middleware installed (auth, partition, correlation-id)"
        )
