"""`osdu_perf setup kusto` -- provision the V2 telemetry tables."""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path

from ...config import load_config
from ...errors import ConfigError
from ...kusto import build_provisioning_script, provision_tables


def run(args: argparse.Namespace) -> int:
    if getattr(args, "target", None) != "kusto":
        raise ConfigError(f"Unknown setup target '{args.target}'. Supported: kusto.")

    project_dir = Path(args.directory).resolve()
    config = load_config(project_dir)
    kusto_cfg = config.kusto_export
    if args.cluster_uri:
        kusto_cfg = replace(kusto_cfg, cluster_uri=args.cluster_uri, ingest_uri=None)
    if args.database:
        kusto_cfg = replace(kusto_cfg, database=args.database)

    if not kusto_cfg.is_configured:
        raise ConfigError(
            "Kusto is not configured. Set kusto_export.cluster_uri and "
            "kusto_export.database in azure_config.yaml, or pass --cluster-uri "
            "and --database."
        )

    commands = build_provisioning_script()
    print(f"Provisioning {len(commands)} Kusto command(s) against")
    print(f"  Cluster : {kusto_cfg.cluster_uri}")
    print(f"  Database: {kusto_cfg.database}")
    print()

    if args.print_only:
        print("-- Dry run (--print-only). Copy the commands below into Kusto Explorer")
        print("-- or pipe through `kusto` CLI to apply them.")
        for cmd in commands:
            print(cmd)
            print()
        return 0

    executed = provision_tables(
        kusto_cfg,
        use_managed_identity=os.getenv("AZURE_LOAD_TEST", "").lower() == "true",
    )
    print(f"Applied {len(executed)} command(s).")
    print("Tables ready: LocustMetricsV2, LocustTestSummaryV2,")
    print("              LocustExceptionsV2, LocustRequestTimeSeriesV2")
    return 0


__all__ = ["run"]
