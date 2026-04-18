"""Thin subprocess wrappers around ``docker``, ``az``, and ``kubectl``.

The k8s subsystem deliberately shells out to the operator's existing CLIs
rather than pulling in the Kubernetes Python client and the ACR SDK. This
keeps the dependency surface tiny and mirrors how a human would run the
same commands.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from ..errors import OsduPerfError
from ..telemetry import get_logger

_LOGGER = get_logger("k8s.cli")


class CliNotFoundError(OsduPerfError):
    """Raised when an external CLI (``docker``/``az``/``kubectl``) is missing."""


class CliExecutionError(OsduPerfError):
    """Raised when an external CLI exits with a non-zero status."""


def require(name: str) -> str:
    """Resolve ``name`` on ``PATH``; raise :class:`CliNotFoundError` if absent."""
    path = shutil.which(name)
    if not path:
        raise CliNotFoundError(
            f"Required CLI '{name}' was not found on PATH. "
            f"Install it before running 'osdu_perf run k8s'."
        )
    return path


def run(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    stdin: str | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``argv`` and return the completed process.

    When ``capture`` is False the child's stdout/stderr stream directly to
    the parent's TTY (great for ``docker build`` progress and ``kubectl
    logs -f``). When True, output is captured into ``result.stdout`` /
    ``result.stderr`` so callers can parse it.
    """
    _LOGGER.debug("exec: %s", " ".join(argv))
    resolved = list(argv)
    resolved[0] = shutil.which(resolved[0]) or resolved[0]
    result = subprocess.run(  # noqa: S603 — argv is constructed by us, no shell
        resolved,
        cwd=str(cwd) if cwd else None,
        input=stdin,
        text=True,
        capture_output=capture,
        check=False,
    )
    if check and result.returncode != 0:
        cmd = " ".join(argv)
        stderr = (result.stderr or "").strip() if capture else ""
        suffix = f"\n  stderr: {stderr}" if stderr else ""
        raise CliExecutionError(f"'{cmd}' exited with status {result.returncode}.{suffix}")
    return result


def stream(argv: Sequence[str]) -> int:
    """Run ``argv`` streaming output and return the exit code (no raise)."""
    _LOGGER.debug("stream: %s", " ".join(argv))
    resolved = list(argv)
    resolved[0] = shutil.which(resolved[0]) or resolved[0]
    return subprocess.call(resolved)  # noqa: S603 — argv is constructed by us


__all__ = ["CliExecutionError", "CliNotFoundError", "require", "run", "stream"]
