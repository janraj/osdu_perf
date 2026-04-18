# Runtime dependencies for both `osdu_perf run azure` and `osdu_perf run k8s`.
# We list PyPI packages explicitly here so the test engine's pip install step
# never needs to resolve the local osdu_perf-*.whl path (ALT and the AKS image
# install the local wheel separately). For `osdu_perf run local` you can simply
# `pip install osdu_perf` in your dev venv instead.
locust>=2.0.0
azure-identity>=1.13.0
azure-core>=1.28.0
azure-mgmt-core>=1.4.0
azure-mgmt-resource>=23.0.0
azure-mgmt-loadtesting>=1.0.0
azure-developer-loadtesting>=1.2.0b1
requests>=2.28.0
pyyaml>=6.0
azure-kusto-data>=5.0.0
azure-kusto-ingest>=5.0.0
