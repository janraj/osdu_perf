# osdu_perf/locust_integration/request_interceptor.py
"""
Per-request correlation-id enrichment via Locust HttpSession monkey-patch.

Automatically appends a unique suffix to the existing ``correlation-id``
header on every HTTP request so that individual requests can be traced
while still being grouped under the same test-run correlation-id.

Activation is automatic – importing this module (done by the package
__init__) registers a ``@events.init`` listener that patches
``HttpSession.request`` exactly once.

No test-code changes are required.
"""

import uuid
import logging
from locust import events
from locust.clients import HttpSession

logger = logging.getLogger(__name__)

_original_request = None


def _intercepted_request(self, method, url, **kwargs):
    """Wrap every outgoing request to inject a per-request correlation-id."""
    headers = kwargs.get("headers")
    if headers is None:
        headers = {}
        kwargs["headers"] = headers

    # Send both: original test-run ID + per-request unique ID as comma-separated values
    base_correlation_id = headers.get("correlation-id", "")
    request_uid = uuid.uuid4().hex  # 32-char hex string (128-bit)
    per_request_id = f"{base_correlation_id}-{request_uid}" if base_correlation_id else request_uid
    if base_correlation_id:
        headers["correlation-id"] = f"{base_correlation_id}, {per_request_id}"
    else:
        headers["correlation-id"] = per_request_id

    return _original_request(self, method, url, **kwargs)


@events.init.add_listener
def _install_request_interceptor(environment, **kwargs):
    """Patch HttpSession.request once when Locust initialises."""
    global _original_request
    if _original_request is None:
        _original_request = HttpSession.request
        HttpSession.request = _intercepted_request
        logger.info(
            "[osdu_perf] Per-request correlation-id interceptor installed"
        )
