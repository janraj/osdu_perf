# Platform configuration — Azure Load Testing resource + optional Kusto
# telemetry sink. Everything here is about WHERE tests run, not WHAT they
# exercise. Required only for `osdu_perf run azure`.
#
# azure_infra:
#   subscription_id: ""
#   resource_group: "adme-performance-rg"
#   location: "eastus"
#   allow_resource_creation: false
#   azure_load_test:
#     name: ""            # existing Azure Load Test resource
#   kusto:                # optional telemetry sink
#     cluster_uri: ""     # EITHER cluster_uri OR ingest_uri (the other is derived)
#     database: ""
