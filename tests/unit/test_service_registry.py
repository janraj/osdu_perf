"""Tests for :class:`osdu_perf.testing.ServiceRegistry`."""

from pathlib import Path

from osdu_perf.testing import ServiceRegistry


def test_registry_discovers_perf_modules(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "perf_demo_test.py"
    src.write_text(
        """
from osdu_perf import BaseService

class DemoService(BaseService):
    def provide_explicit_token(self): return ""
    def prehook(self, headers=None, partition=None, host=None): pass
    def execute(self, headers=None, partition=None, host=None): pass
    def posthook(self, headers=None, partition=None, host=None): pass
""",
        encoding="utf-8",
    )
    registry = ServiceRegistry()
    registry.discover(client=None, root=tmp_path)
    assert registry.services
    assert registry.services[0].__class__.__name__ == "DemoService"


def test_discover_caches_module_across_calls(tmp_path: Path) -> None:
    """Re-running ``discover()`` must not re-execute the test file.

    Without caching, every Locust ``User.on_start`` re-execs the test
    file and any class-level state (one-shot setup guards, counters)
    silently resets. The cache is what makes those guards actually
    fire only once per worker process.
    """
    src = tmp_path / "perf_cache_demo_test.py"
    src.write_text(
        """
import osdu_perf as _op
_op._svcreg_cache_test_exec_count = getattr(_op, '_svcreg_cache_test_exec_count', 0) + 1

from osdu_perf import BaseService

class CachedService(BaseService):
    def provide_explicit_token(self): return ""
    def prehook(self, headers=None, partition=None, host=None): pass
    def execute(self, headers=None, partition=None, host=None): pass
    def posthook(self, headers=None, partition=None, host=None): pass
""",
        encoding="utf-8",
    )

    import osdu_perf

    # Reset cache + counter so a previous test doesn't taint this one.
    ServiceRegistry._module_cache.clear()
    if hasattr(osdu_perf, "_svcreg_cache_test_exec_count"):
        delattr(osdu_perf, "_svcreg_cache_test_exec_count")

    for _ in range(3):
        ServiceRegistry().discover(client=None, root=tmp_path)

    # Module body executed exactly once across the three discover() calls.
    assert osdu_perf._svcreg_cache_test_exec_count == 1

