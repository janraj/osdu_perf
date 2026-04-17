"""Scaffold a new osdu_perf test project from bundled templates."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from string import Template

from ..errors import ScaffoldError
from ..telemetry import get_logger

_LOGGER = get_logger("scaffolding")


@dataclass(frozen=True)
class Sample:
    """A built-in project template."""

    name: str
    title: str
    endpoint: str
    class_name: str


SAMPLES: dict[str, Sample] = {
    "storage_crud": Sample(
        name="storage_crud",
        title="Storage CRUD",
        endpoint="/api/storage/v2/records",
        class_name="StorageCrudService",
    ),
    "search_query": Sample(
        name="search_query",
        title="Search Query",
        endpoint="/api/search/v2/query",
        class_name="SearchQueryService",
    ),
    "schema_browse": Sample(
        name="schema_browse",
        title="Schema Browse",
        endpoint="/api/schema-service/v1/schema",
        class_name="SchemaBrowseService",
    ),
}


def available_samples() -> list[Sample]:
    return list(SAMPLES.values())


class Scaffolder:
    """Writes a new test project into ``target_directory``."""

    def __init__(self, target_directory: Path, *, force: bool = False) -> None:
        self._root = target_directory
        self._force = force

    def create(self, sample_name: str = "storage_crud") -> Path:
        if sample_name not in SAMPLES:
            raise ScaffoldError(
                f"Unknown sample '{sample_name}'. Available: "
                f"{', '.join(sorted(SAMPLES))}"
            )
        sample = SAMPLES[sample_name]
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "config").mkdir(exist_ok=True)

        substitutions = {
            "SAMPLE_NAME": sample.name,
            "SAMPLE_TITLE": sample.title,
            "SAMPLE_ENDPOINT": sample.endpoint,
            "CLASS_NAME": sample.class_name,
            "SCENARIO_NAME": sample.name,
        }

        self._write("azure_config.yaml.tpl", self._root / "config" / "azure_config.yaml", substitutions)
        self._write("test_config.yaml.tpl", self._root / "config" / "test_config.yaml", substitutions)
        self._write("locustfile.py.tpl", self._root / "locustfile.py", substitutions)
        self._write("perf_service_test.py.tpl", self._root / f"perf_{sample.name}_test.py", substitutions)
        self._write("requirements.txt.tpl", self._root / "requirements.txt", substitutions)
        self._write("README.md.tpl", self._root / "README.md", substitutions)

        _LOGGER.info("Scaffolded sample '%s' at %s", sample.name, self._root)
        return self._root

    # ------------------------------------------------------------------
    def _write(self, template_name: str, target: Path, substitutions: dict[str, str]) -> None:
        if target.exists() and not self._force:
            raise ScaffoldError(
                f"Refusing to overwrite '{target}'. Pass --force to replace it."
            )
        template_text = _read_template(template_name)
        rendered = Template(template_text).safe_substitute(substitutions)
        target.write_text(rendered, encoding="utf-8")


def _read_template(name: str) -> str:
    with resources.files("osdu_perf.scaffolding.templates").joinpath(name).open("r", encoding="utf-8") as f:
        return f.read()


__all__ = ["Scaffolder", "Sample", "available_samples", "SAMPLES"]
