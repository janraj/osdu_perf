"""Test-file discovery and upload for Azure Load Testing."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from azure.developer.loadtesting import LoadTestAdministrationClient

from ..telemetry import get_logger

_LOGGER = get_logger("azure.files")

_DEFAULT_SEARCH_PATTERNS = (
    "*.py",
    "perf_*.json",
    "requirements.txt",
    "*.whl",
    "azure_config.yaml",
    "test_config.yaml",
    "config/azure_config.yaml",
    "config/test_config.yaml",
)
_SECURITY_EXCLUDES = {".env", ".config"}


class TestFileUploader:
    """Discovers local test artefacts and uploads them to an ALT resource."""

    def __init__(self, admin_client: LoadTestAdministrationClient) -> None:
        self._client = admin_client

    def discover(
        self,
        root: Path,
        patterns: Iterable[str] = _DEFAULT_SEARCH_PATTERNS,
    ) -> list[Path]:
        """Return local files that should be uploaded with the test."""
        results: list[Path] = []
        seen: set[Path] = set()
        for pattern in patterns:
            for path in root.glob(pattern):
                if not path.is_file() or path in seen:
                    continue
                if path.name.lower() in _SECURITY_EXCLUDES:
                    continue
                seen.add(path)
                results.append(path)
        _LOGGER.info("Discovered %d test file(s) in %s", len(results), root)
        return results

    def upload(self, test_name: str, files: list[Path]) -> list[dict[str, Any]]:
        """Upload each file, ordering ``locustfile.py`` last (ALT requirement)."""
        ordered = sorted(files, key=lambda p: p.name.lower() == "locustfile.py")
        uploaded: list[dict[str, Any]] = []
        for path in ordered:
            # Azure Load Testing identifies Locust entry-point scripts via
            # ``TEST_SCRIPT`` (``JMX_FILE`` is for JMeter only). Using the
            # wrong type for a Locust test yields InvalidTestScriptFile.
            file_type = (
                "TEST_SCRIPT" if path.name.lower() == "locustfile.py" else "ADDITIONAL_ARTIFACTS"
            )
            _LOGGER.info("Uploading %s as %s", path.name, file_type)
            with path.open("rb") as handle:
                result = self._client.begin_upload_test_file(
                    test_id=test_name,
                    file_name=path.name,
                    file_type=file_type,
                    body=handle,
                ).result()
            uploaded.append({"fileName": path.name, "fileType": file_type, "result": result})
        return uploaded


__all__ = ["TestFileUploader"]
