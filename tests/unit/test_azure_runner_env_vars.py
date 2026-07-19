"""Unit tests: scenario-level env vars are forwarded into the Azure Load
Testing (ALT) payload built by AzureLoadTestRunner.create_test().

These mock the Azure credential, resource manager, and urllib transport so no
cloud calls are made; they assert the PATCH body's environmentVariables map.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

RUNNER_MOD = "osdu_perf.operations.azure_test_operation.azure_test_runner"


@pytest.fixture
def runner():
    with patch(f"{RUNNER_MOD}.AzureCliCredential", MagicMock()), \
         patch(f"{RUNNER_MOD}.AzureLoadTestResourceManager", MagicMock()):
        from osdu_perf.operations.azure_test_operation.azure_test_runner import (
            AzureLoadTestRunner,
        )

        r = AzureLoadTestRunner(
            subscription_id="sub",
            resource_group_name="rg",
            load_test_name="lt",
            location="eastus",
            sku="flex",
            version="1.0",
            test_runid_name="run",
        )
    return r


def _capture_payload(runner, **create_test_kwargs):
    """Invoke create_test with mocked transport; return the parsed PATCH body."""
    captured = {}

    def fake_urlopen(req, timeout=30):
        captured["body"] = json.loads(req.data.decode("utf-8")) if req.data else {}

        class _Resp:
            def getcode(self):
                return 201

            def read(self):
                return b"{}"

            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp()

    with patch.object(type(runner), "data_plane_url", new="https://dp.example", create=True), \
         patch(f"{RUNNER_MOD}.urllib.request.urlopen", side_effect=fake_urlopen):
        runner.create_test(
            test_name="t1",
            test_files=[],
            host="https://flex2xv5.oep.ppe.azure-int.net",
            partition="dp1",
            app_id="2f59abbc-7b40-4d0e-91b2-22ca3084bc84",
            token="tok",
            users=200,
            spawn_rate=20,
            run_time="300s",
            engine_instances=4,
            tags="record_size_1KB",
            adme_token="adme",
            **create_test_kwargs,
        )
    return captured["body"]


def test_scenario_env_vars_present_in_alt_payload(runner):
    body = _capture_payload(
        runner,
        scenario_env_vars={"RECORD_SIZE_BYTES": "1024", "CUSTOM_FLAG": "on"},
    )
    env = body["environmentVariables"]
    assert env["RECORD_SIZE_BYTES"] == "1024"
    assert env["CUSTOM_FLAG"] == "on"


def test_scenario_env_vars_do_not_clobber_core_vars(runner):
    # A scenario must not be able to override core operational variables.
    body = _capture_payload(
        runner,
        scenario_env_vars={"LOCUST_HOST": "http://evil", "PARTITION": "hacked"},
    )
    env = body["environmentVariables"]
    assert env["LOCUST_HOST"] == "https://flex2xv5.oep.ppe.azure-int.net"
    assert env["PARTITION"] == "dp1"


def test_no_scenario_env_vars_keeps_core_payload(runner):
    body = _capture_payload(runner, scenario_env_vars=None)
    env = body["environmentVariables"]
    # Core vars still present; no crash on None.
    for key in ("LOCUST_HOST", "PARTITION", "APPID", "AZURE_LOAD_TEST"):
        assert key in env
