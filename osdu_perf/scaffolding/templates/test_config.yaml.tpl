# Defaults used unless overridden by a profile or scenario.
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

# Per-tier overrides. Selected by `test_metadata.performance_tier`.
performance_tier_profiles:
  standard:
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
    users: 10
    spawn_rate: 2
    run_time: "60s"
    metadata:
      scenario_kind: "${SCENARIO_NAME}"
