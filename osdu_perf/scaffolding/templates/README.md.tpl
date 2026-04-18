# ${SAMPLE_TITLE} Performance Tests

Scaffolded by `osdu_perf init --sample=${SAMPLE_NAME}`.

## Layout

```
./
├── config/
│   ├── azure_config.yaml    # Azure Load Test + Kusto export settings
│   └── test_config.yaml     # OSDU env, labels, profiles, scenario defaults
├── locustfile.py            # Locust entrypoint
├── perf_${SAMPLE_NAME}_test.py  # service-specific tasks
├── requirements.txt
└── README.md
```

## Usage

```bash
pip install -r requirements.txt

# 1) Run locally against your OSDU instance
osdu_perf run local --scenario ${SAMPLE_NAME}

# 2) Run on Azure Load Testing
osdu_perf run azure --scenario ${SAMPLE_NAME}

# 3) Run distributed on AKS (1 master + N-1 workers)
#    Requires the `aks:` block in azure_config.yaml + Workload Identity.
osdu_perf run k8s --scenario ${SAMPLE_NAME}

# 4) Run on AKS in web-UI mode (drive runs from the browser)
osdu_perf run k8s --scenario ${SAMPLE_NAME} --web-ui --no-logs
kubectl port-forward -n perf svc/<run-name>-master 8089:8089
# then open http://localhost:8089
```

Edit `config/test_config.yaml` first — the `osdu_environment` block
must point at a real OSDU instance before the tests will work. For
`run azure` / `run k8s`, also fill in the corresponding block in
`config/azure_config.yaml`.

### Web-UI custom fields

In web-UI mode, the Locust swarm form exposes two extra fields under
**Custom parameters**:

* **Osdu test name** — backs `OSDU_PERF_TEST_NAME`
* **Osdu test run id prefix** — backs `OSDU_PERF_TEST_RUN_ID_PREFIX`

Defaults populate from the pod's environment, so leaving them alone
behaves identically. Change either, click **Start swarming**, and the
next run's `TestRunId` (Kusto) reflects the new values without
restarting any pod.

### Multi-cluster

Pass `--azure-config PATH` to point at an alternate config file:

```bash
osdu_perf run k8s --azure-config config/azure_config_aks2.yaml
```
