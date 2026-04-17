"""Tests for :class:`osdu_perf.scaffolding.Scaffolder`."""

from pathlib import Path

import pytest

from osdu_perf.errors import ScaffoldError
from osdu_perf.scaffolding import Scaffolder, available_samples


def test_available_samples_non_empty() -> None:
    names = [s.name for s in available_samples()]
    assert names == ["search_query"]


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


def test_unknown_sample_raises(tmp_path: Path) -> None:
    with pytest.raises(ScaffoldError):
        Scaffolder(tmp_path).create(sample_name="does-not-exist")


def test_refuses_overwrite_without_force(tmp_path: Path) -> None:
    Scaffolder(tmp_path).create(sample_name="search_query")
    with pytest.raises(ScaffoldError):
        Scaffolder(tmp_path).create(sample_name="search_query")
    Scaffolder(tmp_path, force=True).create(sample_name="search_query")
