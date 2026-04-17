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
