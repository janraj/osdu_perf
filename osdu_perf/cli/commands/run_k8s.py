"""``osdu_perf run k8s`` — run distributed Locust on AKS."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...config import load_config, load_from_paths
from ...config._loader import _discover  # noqa: PLC2701 - share discovery
from ...errors import ConfigError
from ...k8s import K8sRunInputs, K8sRunner
from ._run_common import (
    apply_profile_overrides,
    parse_label_overrides,
    resolved_test_name,
    resolved_test_run_id_prefix,
)


def run(args: argparse.Namespace) -> int:
    project_dir = Path(args.directory).resolve()
    azure_config_arg = getattr(args, "azure_config", None)
    azure_config_relpath: str | None = None
    if azure_config_arg:
        azure_path = Path(azure_config_arg)
        if not azure_path.is_absolute():
            azure_path = (project_dir / azure_path).resolve()
        if not azure_path.exists():
            raise ConfigError(f"--azure-config file not found: {azure_path}")
        try:
            azure_config_relpath = azure_path.relative_to(project_dir).as_posix()
        except ValueError as exc:
            raise ConfigError(
                f"--azure-config must live inside --directory ({project_dir}); "
                f"got {azure_path}"
            ) from exc
        _, test_path = _discover(project_dir)
        config = load_from_paths(azure_path, test_path)
    else:
        config = load_config(project_dir)

    env = config.osdu_env
    host = args.host or env.host
    partition = args.partition or env.partition
    app_id = args.app_id or env.app_id
    if not (host and partition and app_id):
        raise ConfigError("host, partition, and app_id must all be provided.")

    resolved = config.resolve(scenario=args.scenario, profile=args.profile)
    profile = apply_profile_overrides(resolved.profile, args)
    prefix = resolved_test_run_id_prefix(resolved, args)
    test_name = resolved_test_name(resolved, args)
    extra_labels = parse_label_overrides(args)
    merged_labels: dict[str, str] = {str(k): str(v) for k, v in resolved.labels.items()}
    merged_labels.update({str(k): str(v) for k, v in extra_labels.items()})

    inputs = K8sRunInputs(
        host=host,
        partition=partition,
        app_id=app_id,
        test_directory=project_dir,
        profile=profile,
        labels=merged_labels,
        scenario=resolved.scenario,
        test_run_id_prefix=prefix,
        profile_name=resolved.profile_name,
        test_name=test_name,
        image_tag=args.image_tag,
        skip_build=args.no_build,
        skip_push=args.no_push,
        skip_logs=args.no_logs,
        web_ui=args.web_ui or config.aks.web_ui,
        azure_config_relpath=azure_config_relpath,
        namespace_override=args.namespace,
        create_service_account=args.create_service_account or config.aks.create_service_account,
    )
    result = K8sRunner(config).run(inputs)
    _print_run_summary(result)
    return 0


def _print_run_summary(result: dict) -> None:
    labels = result.get("labels") or {}
    labels_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if labels else "(none)"
    lines = [
        "",
        "=" * 72,
        "AKS load test run started",
        "=" * 72,
        f"  Run name         : {result.get('runName')}",
        f"  Namespace        : {result.get('namespace')}",
        f"  Image            : {result.get('image')} (pushed={result.get('imagePushed')})",
        f"  Scenario         : {result.get('scenario')}",
        f"  Test name        : {result.get('testName')}",
        f"  Profile          : {result.get('profileName')}",
        f"  Users            : {result.get('users')}",
        f"  Spawn rate       : {result.get('spawnRate')}",
        f"  Run time         : {result.get('runTime')}",
        f"  Engine instances : {result.get('engineInstances')}",
        f"  Host             : {result.get('host')}",
        f"  Partition        : {result.get('partition')}",
        f"  App ID           : {result.get('appId')}",
        f"  Labels           : {labels_str}",
        f"  AKS cluster      : {result.get('aksCluster')} (rg={result.get('resourceGroup')})",
        f"  Subscription     : {result.get('subscriptionId')}",
        f"  Portal           : {result.get('portalUrl')}",
        "=" * 72,
        "",
    ]
    if result.get("webUi"):
        ns = result.get("namespace")
        run_name = result.get("runName")
        lines.extend([
            "Web-UI mode enabled. The master pod is running Locust's web interface.",
            "Port-forward to access the UI in your browser:",
            "",
            f"  kubectl port-forward -n {ns} svc/{run_name}-master 8089:8089",
            "",
            "Then open http://localhost:8089",
            "Stop the run with: "
            f"kubectl delete job -n {ns} {run_name}-master",
            "",
        ])
    print("\n".join(lines))
