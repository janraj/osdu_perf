from types import SimpleNamespace
from unittest.mock import Mock, patch

from osdu_perf.cli.commands.run_azure_command import AzureLoadTestCommand
from osdu_perf.operations.input_handler import InputHandler
from osdu_perf.operations.local_test_operation.local_test_runner import LocalTestRunner


def test_input_handler_generate_test_name_normalizes_values():
    handler = InputHandler.__new__(InputHandler)
    handler.get_test_name_prefix = Mock(return_value="My.Prefix")
    handler.logger = Mock()

    generated, test_run_id = InputHandler.generate_test_name_and_run_id(
        handler,
        sku="Premium",
        version="1.2",
    )

    assert generated == "my_prefix_premium_1_2"
    assert test_run_id.startswith("My.Prefix_")


def test_local_runner_uses_shared_test_name_generation_for_run_id():
    logger = Mock()
    runner = LocalTestRunner(logger=logger)

    input_handler = Mock()
    input_handler.validate_scenario.return_value = "scenario_1"
    input_handler.get_users.return_value = 10
    input_handler.get_spawn_rate.return_value = 2
    input_handler.get_run_time.return_value = "60s"
    input_handler.get_test_scenario.return_value = "scenario_1"
    input_handler.generate_test_name_and_run_id.return_value = (
        "team_prefix",
        "team_prefix_20260417_120000",
    )
    input_handler.resolve_test_execution_settings.return_value = {
        "scenario": "scenario_1",
        "tags": "scenario_1",
        "users": 10,
        "spawn_rate": 2,
        "run_time": "60s",
        "engine_instances": 1,
    }

    runner._input_handler = input_handler
    runner._get_input_handler = Mock(return_value=input_handler)
    runner._extract_osdu_parameters = Mock(
        return_value=("https://example", "opendes", "app-id", "token")
    )

    args = SimpleNamespace(
        system_config="config/system_config.yaml",
        scenario=["scenario_1"],
        users=None,
        spawn_rate=None,
        run_time=None,
        sku=None,
        version=None,
    )

    config = runner._load_test_configuration(args)

    input_handler.generate_test_name_and_run_id.assert_called_once_with(sku="", version="")
    assert config.test_run_id == "team_prefix_20260417_120000"


@patch("osdu_perf.operations.input_handler.InputHandler")
def test_azure_command_uses_shared_test_name_generation(mock_input_handler_class):
    input_handler = Mock()
    mock_input_handler_class.return_value = input_handler

    input_handler.get_osdu_host.return_value = "https://example"
    input_handler.get_osdu_partition.return_value = "opendes"
    input_handler.get_osdu_app_id.return_value = "app-id"
    input_handler.get_osdu_sku.return_value = "standard"
    input_handler.get_osdu_version.return_value = "1.0"
    input_handler.get_azure_subscription_id.return_value = "sub-id"
    input_handler.get_azure_resource_group.return_value = "rg"
    input_handler.get_azure_location.return_value = "eastus"
    input_handler.validate_scenario.return_value = "scenario_1"
    input_handler.get_users.return_value = 10
    input_handler.get_spawn_rate.return_value = 2
    input_handler.get_run_time.return_value = "60s"
    input_handler.get_engine_instances.return_value = 1
    input_handler.generate_test_name_and_run_id.return_value = (
        "team_prefix_standard_1_0",
        "team_prefix_standard_1_0_20260417_120000",
    )
    input_handler.resolve_test_execution_settings.return_value = {
        "scenario": "scenario_1",
        "tags": "scenario_1",
        "users": 10,
        "spawn_rate": 2,
        "run_time": "60s",
        "engine_instances": 1,
    }
    input_handler.get_test_scenario.return_value = "scenario_1"
    input_handler.get_test_run_id_description.return_value = "desc"
    input_handler.get_test_run_name.return_value = "team_prefix_standard-0417_120000"

    command = AzureLoadTestCommand(logger=Mock())
    args = SimpleNamespace(
        system_config="config/system_config.yaml",
        host=None,
        partition=None,
        token="token",
        app_id=None,
        sku=None,
        version=None,
        subscription_id=None,
        resource_group=None,
        location=None,
        scenario=["scenario_1"],
        users=None,
        spawn_rate=None,
        run_time=None,
        engine_instances=None,
    )

    config = command._load_azure_configuration(args)

    input_handler.generate_test_name_and_run_id.assert_called_once_with(
        sku="standard",
        version="1.0",
    )
    assert config["test_name"] == "team_prefix_standard_1_0"
