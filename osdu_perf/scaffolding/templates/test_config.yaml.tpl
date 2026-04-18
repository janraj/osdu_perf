# OSDU environment — WHERE the test hits (target OSDU instance).
osdu_environment:
  host: "https://your-osdu-host.com"
  partition: "your-partition-id"
  app_id: "your-azure-app-id"

# Free-form labels attached verbatim to every Kusto telemetry row.
# The framework never interprets these keys — use whatever makes your
# dashboards useful (version, build_id, region, commit sha, ...).
labels:
  version: "25.2.35"

# Named load shapes. Pick one via --profile, via scenario_defaults, or
# via run_scenario. Naming convention: U<users>_T<duration>.
profiles:
  U50_T15M:
    users: 50
    spawn_rate: 5
    run_time: "15m"
    engine_instances: 1
  U100_T15M:
    users: 100
    spawn_rate: 10
    run_time: "15m"
    engine_instances: 1
  U200_T30M:
    users: 200
    spawn_rate: 20
    run_time: "30m"
    engine_instances: 2

# Per-scenario defaults. Each entry says: "when someone runs scenario X
# without --profile, use this profile + extra telemetry labels."
# Scenarios themselves are Python files under perf_tests/ — they are
# discovered automatically; this block is NOT a registry.
scenario_defaults:
  ${SCENARIO_NAME}:
    profile: U50_T15M
    metadata:
      scenario_kind: "${SCENARIO_NAME}"

# Default invocation when `osdu_perf run local|azure` is called WITHOUT
# --scenario. Everything in this block only applies when this block
# supplies the scenario; an explicit --scenario bypasses it entirely.
run_scenario:
  scenario: ${SCENARIO_NAME}
  profile: U50_T15M              # which load shape from `profiles:` above.
                                 # Override with --profile. Falls back to
                                 # scenario_defaults.<scenario>.profile when omitted.
  test_name: smoke               # stable ALT test id component. Final test id =
                                 #   <scenario>_<test_name>  (defaults to <scenario>_<scenario>).
                                 # Override per invocation with --test-name. Every run
                                 # nests under this one ALT test definition.
  test_run_id_prefix: "perf"     # token in the generated test RUN id:
                                 #   <scenario>_<test_name>_<test_run_id_prefix>_<UTC_YYYYMMDDHHMMSS>
                                 # Override per invocation with --test-run-id-prefix.
  # labels:                      # optional extra labels merged on top
  #   triggered_by: "nightly-ci"
