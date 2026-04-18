"""Build the test image and push it to Azure Container Registry."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from ..config import ContainerRegistryConfig
from ..errors import ConfigError
from ..telemetry import get_logger
from . import cluster

_LOGGER = get_logger("k8s.builder")
_TEMPLATE_PKG = "osdu_perf.k8s.templates"


def stage_build_context(project_dir: Path, dest_dir: Path) -> None:
    """Copy Dockerfile, entrypoint, and ``.dockerignore`` into ``dest_dir``.

    Existing files in ``dest_dir`` are overwritten so re-runs always pick
    up the latest packaged assets. ``project_dir`` is kept as a parameter
    for future use (e.g. path-dependent build overrides) and currently
    behaves the same as ``dest_dir``.
    """
    del project_dir  # unused today; preserved for API compatibility
    for name, mode in (
        ("Dockerfile", 0o644),
        ("_entrypoint.sh", 0o755),
        (".dockerignore", 0o644),
    ):
        target = dest_dir / name
        target.write_bytes(
            files(_TEMPLATE_PKG).joinpath(name).read_bytes()
        )
        with contextlib.suppress(OSError):
            target.chmod(mode)


@dataclass(frozen=True)
class ImageBuildResult:
    image_ref: str
    pushed: bool


class ImageBuilder:
    """Build + push the user's project as a container image to ACR."""

    def __init__(self, registry: ContainerRegistryConfig) -> None:
        if not registry.is_configured:
            raise ConfigError(
                "aks.container_registry.name and aks.container_registry.login_server are "
                "required for 'osdu_perf run k8s'. Add a 'container_registry:' block under "
                "'aks:' in azure_config.yaml."
            )
        self._registry = registry

    def build_and_push(
        self,
        project_dir: Path,
        tag: str,
        *,
        skip_build: bool = False,
        skip_push: bool = False,
        use_acr_build: bool = False,
    ) -> ImageBuildResult:
        image_ref = f"{self._registry.login_server}/{self._registry.image_repository}:{tag}"
        if skip_build:
            _LOGGER.info("Skipping image build (--no-build); using %s", image_ref)
            return ImageBuildResult(image_ref=image_ref, pushed=False)

        # Always stage the Dockerfile / entrypoint / .dockerignore so the build
        # context is self-contained whether we use local docker or `az acr build`.
        stage_build_context(project_dir, project_dir)

        if use_acr_build:
            cluster.require("az")
            image_no_registry = f"{self._registry.image_repository}:{tag}"
            _LOGGER.info(
                "Building + pushing %s via 'az acr build' (no local docker required)",
                image_ref,
            )
            cluster.run(
                [
                    "az",
                    "acr",
                    "build",
                    "--registry",
                    str(self._registry.name),
                    "--image",
                    image_no_registry,
                    "--file",
                    "Dockerfile",
                    "--only-show-errors",
                    ".",
                ],
                cwd=project_dir,
            )
            return ImageBuildResult(image_ref=image_ref, pushed=True)

        cluster.require("docker")
        _LOGGER.info("Building image %s from %s", image_ref, project_dir)
        cluster.run(
            ["docker", "build", "-t", image_ref, "-f", "Dockerfile", "."],
            cwd=project_dir,
        )

        if skip_push:
            _LOGGER.info("Skipping push (--no-push); image stays local")
            return ImageBuildResult(image_ref=image_ref, pushed=False)

        cluster.require("az")
        _LOGGER.info("Logging in to ACR %s", self._registry.name)
        cluster.run(["az", "acr", "login", "--name", str(self._registry.name)])

        _LOGGER.info("Pushing %s", image_ref)
        cluster.run(["docker", "push", image_ref])
        return ImageBuildResult(image_ref=image_ref, pushed=True)


__all__ = ["ImageBuilder", "ImageBuildResult"]
