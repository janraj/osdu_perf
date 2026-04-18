"""Render k8s YAML manifests from string templates.

Templates use ``string.Template`` (``${VAR}`` substitution) and live in
``osdu_perf/k8s/templates/*.yaml.tpl``. The renderer copies the unmodified
files for the Dockerfile + entrypoint when staging the build context.
"""

from __future__ import annotations

import contextlib
from importlib.resources import files
from pathlib import Path
from string import Template

_TEMPLATE_PKG = "osdu_perf.k8s.templates"

_MANIFEST_FILES = ("namespace.yaml.tpl", "configmap.yaml.tpl", "master.yaml.tpl")


def _read(name: str) -> str:
    return files(_TEMPLATE_PKG).joinpath(name).read_text(encoding="utf-8")


def _render(name: str, values: dict[str, str]) -> str:
    return Template(_read(name)).substitute(values)


def render_all(values: dict[str, str], *, worker_count: int) -> str:
    """Render every shared manifest plus the worker Job (skipped when ``worker_count == 0``).

    Returns a single multi-document YAML string ready for ``kubectl apply -f -``.
    """
    docs = [_render(name, values) for name in _MANIFEST_FILES]
    if worker_count > 0:
        worker_values = {**values, "WORKER_COUNT": str(worker_count)}
        docs.append(_render("workers.yaml.tpl", worker_values))
    return "\n---\n".join(docs)


def stage_build_context(project_dir: Path, dest_dir: Path) -> None:
    """Copy Dockerfile, entrypoint, and ``.dockerignore`` into ``dest_dir``.

    Existing files in ``dest_dir`` are overwritten so re-runs always pick
    up the latest packaged template.
    """
    for tpl_name, dest_name, mode in (
        ("Dockerfile", "Dockerfile", 0o644),
        ("_entrypoint.sh", "_entrypoint.sh", 0o755),
        (".dockerignore", ".dockerignore", 0o644),
    ):
        target = dest_dir / dest_name
        target.write_bytes(_read(tpl_name).encode("utf-8"))
        with contextlib.suppress(OSError):
            target.chmod(mode)


__all__ = ["render_all", "stage_build_context"]
