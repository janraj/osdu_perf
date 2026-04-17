# OSDU environment — fill in your OSDU instance details.
osdu_environment:
  host: "https://your-osdu-host.com"
  partition: "your-partition-id"
  app_id: "your-azure-app-id"

# Free-form labels describing *what* is being tested. Every key/value is
# lifted into the Kusto `Metadata` column. `performance_tier` also selects
# the matching profile from test_config.yaml.
test_metadata:
  performance_tier: "standard"
  version: "25.2.35"

# Azure infrastructure. Required for `osdu_perf run azure`.
# azure_infra:
#   subscription_id: ""
#   resource_group: "adme-performance-rg"
#   location: "eastus"
#   allow_resource_creation: false
#   azure_load_test:
#     name: ""            # name of an existing Azure Load Test resource
#   kusto:                 # optional telemetry sink
#     cluster_uri: ""      # EITHER cluster_uri OR ingest_uri (the other is derived)
#     database: ""
