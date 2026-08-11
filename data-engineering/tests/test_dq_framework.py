"""Data quality framework tests — config, run_checks, freshness."""

import ast
import os
import yaml

DQ_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dq")
SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

CONFIG_PATH = os.path.join(DQ_DIR, "config.yaml")
RUN_CHECKS_PATH = os.path.join(DQ_DIR, "run_checks.py")
FRESHNESS_PATH = os.path.join(SCRIPTS_DIR, "freshness.py")


class TestDQConfig:
    def test_config_exists(self):
        assert os.path.exists(CONFIG_PATH)

    def test_config_valid_yaml(self):
        config = yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))
        assert "checks" in config
        assert len(config["checks"]) > 0

    def test_config_has_all_check_types(self):
        config = yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))
        check_names = [c["name"] for c in config["checks"]]
        assert "null_rate_title_basics" in check_names
        assert "null_rate_title_rating" in check_names
        assert "orphan_title_episode" in check_names
        assert "row_count_title_basics" in check_names

    def test_config_check_fields(self):
        config = yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))
        for check in config["checks"]:
            assert "name" in check
            assert "table" in check
            assert "metric" in check
            assert "threshold" in check
            assert "severity" in check

    def test_config_thresholds_valid(self):
        config = yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))
        for check in config["checks"]:
            assert isinstance(check["threshold"], (int, float))
            assert 0 <= check["threshold"] <= 1.0 or check["metric"] == "row_count_variance"


class TestDQRunner:
    def test_runner_exists(self):
        assert os.path.exists(RUN_CHECKS_PATH)

    def test_runner_parses(self):
        with open(RUN_CHECKS_PATH, encoding="utf-8") as f:
            ast.parse(f.read())

    def test_runner_has_metrics(self):
        with open(RUN_CHECKS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "null_rate" in content
        assert "orphan_rate" in content
        assert "row_count_variance" in content

    def test_runner_has_quarantine_logic(self):
        with open(RUN_CHECKS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "quarantine" in content.lower()
        assert "INSERT INTO silver.quarantine" in content

    def test_runner_has_logging(self):
        with open(RUN_CHECKS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "data_quality_log" in content
        assert "INSERT INTO silver.data_quality_log" in content

    def test_runner_has_main_function(self):
        with open(RUN_CHECKS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "def main" in content
        assert "if __name__" in content

    def test_runner_has_argparse(self):
        with open(RUN_CHECKS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "argparse" in content
        assert "--jdbc-url" in content


class TestFreshnessMonitor:
    def test_freshness_exists(self):
        assert os.path.exists(FRESHNESS_PATH)

    def test_freshness_parses(self):
        with open(FRESHNESS_PATH, encoding="utf-8") as f:
            ast.parse(f.read())

    def test_freshness_has_sla_check(self):
        with open(FRESHNESS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "sla_hours" in content
        assert "sla_boundary" in content or "timedelta" in content

    def test_freshness_checks_all_tables(self):
        with open(FRESHNESS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "title_basics" in content
        assert "name_basics" in content
        assert "title_rating" in content

    def test_freshness_has_main(self):
        with open(FRESHNESS_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "def main" in content
        assert "if __name__" in content
