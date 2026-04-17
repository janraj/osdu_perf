# OSDU environment — fill in your OSDU instance details.
osdu_environment:
  host: "https://your-osdu-host.com"
  partition: "your-partition-id"
  app_id: "your-azure-app-id"

# Free-form labels attached verbatim to every Kusto telemetry row.
# The framework never interprets these keys — use whatever makes your
# dashboards useful (version, build_id, region, etc.).
test_metadata:
  version: "25.2.35"

# Defaults used when neither the selected profile nor the scenario
# overrides a value.
test_settings:
  users: 10
  spawn_rate: 2
  run_time: "60s"
  engine_instances: 1
  default_wait_time:
    min: 1
    max: 3
  test_name_prefix: "${TEST_NAME_PREFIX}"
  test_run_id_description: "Test run for OSDU APIs"

# Named settings bundles. Selected via `--profile <name>`, a scenario's
# `profile:` field, or `default` as a fallback.
profiles:
  default:
    users: 10
    spawn_rate: 2
    run_time: "60s"
  flex:
    users: 50
    spawn_rate: 5
    run_time: "5m"

# Named scenarios. Pick one via `osdu_perf run local --scenario <name>`.
scenarios:
  ${SCENARIO_NAME}:
    profile: default           # optional; CLI --profile overrides this
    users: 10
    spawn_rate: 2
    run_time: "60s"
    metadata:
      scenario_kind: "${SCENARIO_NAME}"
