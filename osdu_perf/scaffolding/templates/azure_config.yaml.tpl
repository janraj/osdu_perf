# Platform configuration. Two independent sections:
#
#   azure_load_test  -> where `osdu_perf run azure` provisions + runs the test
#                       (not used by `osdu_perf run local`).
#   kusto_export     -> optional telemetry sink for EITHER run mode.
#                       When configured, every completed run ingests a
#                       summary row into the database.
#
# Both sections are optional for `osdu_perf run local`. Uncomment and
# fill in only what you need.

# azure_load_test:
#   subscription_id: ""
#   resource_group: "adme-performance-rg"
#   location: "eastus"
#   allow_resource_creation: false   # true lets osdu_perf create RG + ALT
#   name: ""                         # existing Azure Load Test resource

# kusto_export:
#   cluster_uri: ""     # EITHER cluster_uri OR ingest_uri (the other is derived)
#   database: ""
