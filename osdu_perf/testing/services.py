"""Auto-discovery of service test modules (``perf_*_test.py``)."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any

from ..telemetry import get_logger
from .base_service import BaseService

_LOGGER = get_logger("testing.services")


class ServiceRegistry:
    """Discovers and instantiates every :class:`BaseService` subclass found
    in ``perf_*_test.py`` modules inside the current working directory.
    """

    def __init__(self) -> None:
        self._services: list[BaseService] = []

    @property
    def services(self) -> list[BaseService]:
        return list(self._services)

    def discover(self, client: Any = None, root: Path | None = None) -> list[BaseService]:
        """Discover services from the given directory (defaults to cwd)."""
        directory = Path(root or Path.cwd())
        test_files = sorted(
            p
            for p in directory.iterdir()
            if p.is_file() and p.name.startswith("perf_") and p.name.endswith("_test.py")
        )
        if not test_files:
            _LOGGER.info("No perf_*_test.py files found in %s", directory)
            return []

        for path in test_files:
            self._register_from_file(path, client)
        _LOGGER.info("Registered %d service(s)", len(self._services))
        return list(self._services)

    def _register_from_file(self, path: Path, client: Any) -> None:
        module_name = path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            _LOGGER.warning("Cannot load module spec from %s", path)
            return
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # pragma: no cover - surfaces to user
            _LOGGER.error("Failed loading %s: %s", path, exc)
            return

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module_name:
                continue
            if not issubclass(obj, BaseService) or obj is BaseService:
                continue
            try:
                instance = obj(client)
            except Exception as exc:
                _LOGGER.error("Cannot instantiate %s from %s: %s", name, path.name, exc)
                continue
            self._services.append(instance)
            _LOGGER.info("Registered service %s from %s", name, path.name)


__all__ = ["ServiceRegistry"]
