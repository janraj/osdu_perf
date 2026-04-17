# ${SAMPLE_TITLE} Performance Tests

Scaffolded by `osdu_perf init --sample=${SAMPLE_NAME}`.

## Layout

```
./
├── config/
│   ├── system_config.yaml   # OSDU + Azure + Kusto settings
│   └── test_config.yaml     # scenarios, defaults, profiles
├── locustfile.py            # Locust entrypoint
├── perf_${SAMPLE_NAME}_test.py  # service-specific tasks
├── requirements.txt
└── README.md
```

## Usage

```bash
pip install -r requirements.txt

# Run locally against your OSDU instance
osdu_perf run local --scenario ${SAMPLE_NAME}

# Run on Azure Load Testing
osdu_perf run azure --scenario ${SAMPLE_NAME}
```

Edit `config/system_config.yaml` first — the host, partition, and app id
must point at a real OSDU instance before the tests will work.
