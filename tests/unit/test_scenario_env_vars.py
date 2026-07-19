"""Unit tests for scenario-level environment variable overrides.

Covers:
- Arbitrary env/environment key-value pairs exposed via get_scenario_env_vars()
- Scenario-level performance-tier override resolution/priority
- Backward compatibility (global fallback when scenario defines no overrides)
"""

from unittest.mock import patch


def _make_input_handler(system_config=None, test_config=None):
    """Create an InputHandler in config-only mode with the given configs."""
    with patch(
        "osdu_perf.operations.input_handler.InputHandler._load_split_configs"
    ) as mock_load:
        mock_load.return_value = (system_config or {}, test_config or {})
        with patch(
            "osdu_perf.operations.input_handler.InputHandler._detect_azure_load_test_environment",
            return_value=False,
        ):
            from osdu_perf.operations.input_handler import InputHandler

            ih = InputHandler(environment=None)
    return ih


class TestGetScenarioEnvVars:
    """Tests for get_scenario_env_vars()."""

    def test_returns_empty_when_no_scenarios(self):
        ih = _make_input_handler(test_config={})
        assert ih.get_scenario_env_vars() == {}

    def test_returns_empty_when_scenario_has_no_env_block(self):
        ih = _make_input_handler(test_config={"scenarios": {"s1": {"test_name_prefix": "p"}}})
        ih.set_selected_scenario("s1")
        assert ih.get_scenario_env_vars() == {}

    def test_reads_environment_block(self):
        ih = _make_input_handler(
            test_config={
                "scenarios": {
                    "s1": {"environment": {"RECORD_SIZE": 1024, "FLAG": "on"}}
                }
            }
        )
        ih.set_selected_scenario("s1")
        assert ih.get_scenario_env_vars() == {"RECORD_SIZE": "1024", "FLAG": "on"}

    def test_env_alias_takes_precedence_over_environment(self):
        ih = _make_input_handler(
            test_config={
                "scenarios": {
                    "s1": {
                        "env": {"SOURCE": "env"},
                        "environment": {"SOURCE": "environment"},
                    }
                }
            }
        )
        ih.set_selected_scenario("s1")
        assert ih.get_scenario_env_vars() == {"SOURCE": "env"}

    def test_reserved_tier_keys_are_excluded(self):
        ih = _make_input_handler(
            test_config={
                "scenarios": {
                    "s1": {
                        "environment": {
                            "performance_tier_profiles": "flex",
                            "CUSTOM": "keep",
                        }
                    }
                }
            }
        )
        ih.set_selected_scenario("s1")
        env = ih.get_scenario_env_vars()
        assert env == {"CUSTOM": "keep"}
        assert "performance_tier_profiles" not in env

    def test_none_values_are_dropped(self):
        ih = _make_input_handler(
            test_config={"scenarios": {"s1": {"environment": {"A": None, "B": "1"}}}}
        )
        ih.set_selected_scenario("s1")
        assert ih.get_scenario_env_vars() == {"B": "1"}


class TestScenarioPerformanceTierOverride:
    """Tests for scenario-level performance tier override and priority."""

    def test_no_override_returns_none(self):
        ih = _make_input_handler(test_config={"scenarios": {"s1": {}}})
        ih.set_selected_scenario("s1")
        assert ih.get_scenario_performance_tier_override() is None

    def test_override_from_environment_block(self):
        ih = _make_input_handler(
            test_config={
                "scenarios": {"s1": {"environment": {"performance_tier_profiles": "flex"}}}
            }
        )
        ih.set_selected_scenario("s1")
        assert ih.get_scenario_performance_tier_override() == "flex"

    def test_scenario_override_beats_global(self):
        """Scenario tier overrides the global osdu_environment tier."""
        ih = _make_input_handler(
            system_config={"osdu_environment": {"performance_tier": "standard"}},
            test_config={
                "scenarios": {"s1": {"environment": {"performance_tier_profiles": "flex"}}}
            },
        )
        ih.set_selected_scenario("s1")
        assert ih.get_osdu_performance_tier() == "flex"

    def test_cli_override_beats_scenario(self):
        """Explicit CLI override wins over the scenario-level override."""
        ih = _make_input_handler(
            system_config={"osdu_environment": {"performance_tier": "standard"}},
            test_config={
                "scenarios": {"s1": {"environment": {"performance_tier_profiles": "flex"}}}
            },
        )
        ih.set_selected_scenario("s1")
        assert ih.get_osdu_performance_tier(cli_override="developer") == "developer"

    def test_global_used_when_no_scenario_override(self):
        """Backward compat: falls back to global tier when scenario omits it."""
        ih = _make_input_handler(
            system_config={"osdu_environment": {"performance_tier": "standard"}},
            test_config={"scenarios": {"s1": {"test_name_prefix": "p"}}},
        )
        ih.set_selected_scenario("s1")
        assert ih.get_osdu_performance_tier() == "standard"


class TestScenarioTierSelectsProfile:
    """Tests that the scenario tier override drives profile selection."""

    def test_scenario_tier_selects_matching_profile(self):
        ih = _make_input_handler(
            system_config={"osdu_environment": {"performance_tier": "standard"}},
            test_config={
                "performance_tier_profiles": {
                    "standard": {"users": 10, "spawn_rate": 2},
                    "flex": {"users": 200, "spawn_rate": 20},
                },
                "scenarios": {
                    "s1": {"environment": {"performance_tier_profiles": "flex"}}
                },
            },
        )
        ih.set_selected_scenario("s1")
        settings = ih.get_test_settings()
        assert settings["users"] == 200
        assert settings["spawn_rate"] == 20

    def test_env_block_not_leaked_into_test_settings(self):
        ih = _make_input_handler(
            test_config={
                "scenarios": {
                    "s1": {
                        "test_name_prefix": "p",
                        "environment": {"CUSTOM": "x"},
                    }
                }
            }
        )
        ih.set_selected_scenario("s1")
        settings = ih.get_test_settings()
        assert "environment" not in settings
        assert "env" not in settings
        assert settings["test_name_prefix"] == "p"


class TestScenarioNestedProfileOverride:
    """Scenario env `performance_tier_profiles` uses the global schema and
    deep-merges local-over-global for the selected tier."""

    GLOBAL = {
        "performance_tier_profiles": {
            "flex": {
                "default_wait_time": {"min": 1, "max": 3},
                "users": 50,
                "spawn_rate": 2,
                "run_time": "900s",
                "engine_instances": 4,
            },
            "standard": {"users": 1000, "spawn_rate": 1, "run_time": "600s"},
        }
    }

    def _ih(self, scenario_env, tier="flex"):
        cfg = dict(self.GLOBAL)
        cfg["scenarios"] = {"s1": {"environment": scenario_env}}
        ih = _make_input_handler(
            system_config={"osdu_environment": {"performance_tier": tier}},
            test_config=cfg,
        )
        ih.set_selected_scenario("s1")
        return ih

    def test_partial_field_override_wins_over_global(self):
        # Only flex.users + run_time overridden; other flex fields stay global.
        ih = self._ih({"performance_tier_profiles": {"flex": {"users": 999, "run_time": "120s"}}})
        s = ih.get_test_settings()
        assert s["users"] == 999            # local wins
        assert s["run_time"] == "120s"      # local wins
        assert s["spawn_rate"] == 2          # from global flex
        assert s["engine_instances"] == 4    # from global flex

    def test_nested_default_wait_time_partial_override(self):
        ih = self._ih({"performance_tier_profiles": {"flex": {"default_wait_time": {"max": 9}}}})
        s = ih.get_test_settings()
        assert s["default_wait_time"]["max"] == 9   # local
        assert s["default_wait_time"]["min"] == 1   # preserved from global

    def test_override_ignored_when_tier_not_selected(self):
        # Global tier is standard; a flex-only override must not affect standard.
        ih = self._ih({"performance_tier_profiles": {"flex": {"users": 999}}}, tier="standard")
        s = ih.get_test_settings()
        assert s["users"] == 1000  # global standard, untouched

    def test_nested_override_not_forwarded_as_env_var(self):
        ih = self._ih({"performance_tier_profiles": {"flex": {"users": 999}}, "CUSTOM": "keep"})
        assert ih.get_scenario_env_vars() == {"CUSTOM": "keep"}

    def test_global_used_when_scenario_has_no_override(self):
        ih = self._ih({"CUSTOM": "x"})
        s = ih.get_test_settings()
        assert s["users"] == 50  # global flex intact
        assert s["run_time"] == "900s"

