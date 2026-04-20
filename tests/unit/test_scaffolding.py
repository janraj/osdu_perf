"""Tests for :class:`osdu_perf.scaffolding.Scaffolder`."""

from pathlib import Path

import pytest

from osdu_perf.errors import ScaffoldError
from osdu_perf.scaffolding import Scaffolder, available_samples


def test_available_samples_non_empty() -> None:
    names = sorted(s.name for s in available_samples())
    assert names == ["search_query", "storage_get_record_by_id"]


def test_scaffolder_writes_expected_layout(tmp_path: Path) -> None:
    Scaffolder(tmp_path).create(sample_name="search_query")
    for expected in [
        "locustfile.py",
        "perf_search_query_test.py",
        "README.md",
        "requirements.txt",
        "config/azure_config.yaml",
        "config/test_config.yaml",
    ]:
        assert (tmp_path / expected).is_file(), f"missing {expected}"


def test_scaffolder_writes_storage_sample(tmp_path: Path) -> None:
    Scaffolder(tmp_path).create(sample_name="storage_get_record_by_id")
    test_file = tmp_path / "perf_storage_get_record_by_id_test.py"
    assert test_file.is_file()
    contents = test_file.read_text(encoding="utf-8")
    assert "class StorageGetRecordByIdService" in contents
    assert "/api/legal/v1/legaltags" in contents
    assert "/api/storage/v2/records" in contents
    cfg = (tmp_path / "config" / "test_config.yaml").read_text(encoding="utf-8")
    assert "storage_get_record_by_id" in cfg


def test_unknown_sample_raises(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError):
        Scaffolder(tmp_path).create(sample_name="does-not-exist")


def test_refuses_overwrite_without_force(tmp_path: Path) -> None:
    Scaffolder(tmp_path).create(sample_name="search_query")
    with pytest.raises(ScaffoldError):
        Scaffolder(tmp_path).create(sample_name="search_query")
    Scaffolder(tmp_path, force=True).create(sample_name="search_query")
