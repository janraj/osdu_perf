# Platform configuration. Independent sections, each used by a different runner.
#
#   azure_load_test    -> `osdu_perf run azure`  (Azure Load Testing)
#   aks                -> `osdu_perf run k8s`    (cluster + ACR for the test pods)
#   kusto_export       -> all run modes (telemetry sink, optional)
#
# All sections are optional for `osdu_perf run local`. Uncomment and fill in
# only what you need.

# azure_load_test:
#   subscription_id: ""
#   resource_group: "adme-performance-rg"
#   location: "eastus"
#   allow_resource_creation: false   # true lets osdu_perf create RG + ALT
#   name: ""                         # existing Azure Load Test resource

# aks:
#   subscription_id: ""
#   resource_group: ""
#   cluster_name: ""
#   namespace: "perf"               # default; pods + Job land here
#   service_account: "osdu-perf-runner"
#   workload_identity_client_id: "" # client_id of the UAMI federated to <ns>:<sa>
#   create_service_account: false   # true = chart creates the ServiceAccount with the
#                                   # workload-identity annotation (use on a fresh cluster
#                                   # where the SA does not yet exist; overridden by
#                                   # `--create-service-account` CLI flag).
#   web_ui: false                   # true = launch Locust web UI on master pod port 8089
#                                   # (overridden by `--web-ui` CLI flag)
#   container_registry:
#     name: ""                      # short ACR name (used for `az acr login`)
#     login_server: ""              # optional; auto-derived to <name>.azurecr.io
#     image_repository: "osdu-perf" # path within the registry
#   # ------------------------------------------------------------------
#   # Optional: expose the Locust web UI outside the cluster (web_ui=true)
#   # The Helm chart creates the matching ingress resource for you.
#   # ------------------------------------------------------------------
#   ingress:
#     type: "none"                  # "none" | "istio" | "ingress"
#     host: ""                      # e.g. "mythosflex1.oep.ppe.azure-int.net"
#     path_prefix: "/locust"        # UI is served at https://<host><path_prefix>/
#     istio:
#       gateway: "istio-system/istio-gateway"   # <ns>/<name> of an existing Gateway
#       timeout: "3600s"
#     ingress:                      # only used when type == "ingress"
#       class_name: ""              # e.g. "nginx"
#       annotations: {}             # map of annotation -> value

# kusto_export:
#   cluster_uri: ""     # EITHER cluster_uri OR ingest_uri (the other is derived)
#   database: ""
