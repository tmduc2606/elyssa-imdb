"""
Data Quality Framework Tests & Benchmarks
Validates: DQ config, check definitions, quarantine logic, freshness checks
"""
import os
import sys
import time
import pytest
import yaml
import ast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DQ_DIR = os.path.join(os.path.dirname(__file__), '..')
SCRIPTS_DIR = os.path.join(DQ_DIR, '..', 'scripts')

# ─── DQ Config Tests ──────────────────────────────────────────────────────────

class TestDQConfig:
    """Tests for dq/config.yaml"""

    def test_config_exists(self):
        assert os.path.exists(os.path.join(DQ_DIR, 'config.yaml'))

    def test_config_valid_yaml(self):
        path = os.path.join(DQ_DIR, 'config.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
        assert 'checks' in config
        assert len(config['checks']) > 0

    def test_config_has_all_check_types(self):
        path = os.path.join(DQ_DIR, 'config.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
        check_names = [c['name'] for c in config['checks']]
        assert 'null_rate_title_basics' in check_names
        assert 'null_rate_title_rating' in check_names
        assert 'orphan_title_episode' in check_names
        assert 'row_count_title_basics' in check_names

    def test_config_check_fields(self):
        path = os.path.join(DQ_DIR, 'config.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
        for check in config['checks']:
            assert 'name' in check
            assert 'table' in check
            assert 'metric' in check
            assert 'threshold' in check
            assert 'severity' in check

    def test_config_thresholds_valid(self):
        path = os.path.join(DQ_DIR, 'config.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
        for check in config['checks']:
            assert isinstance(check['threshold'], (int, float))
            assert 0 <= check['threshold'] <= 1.0 or check['metric'] == 'row_count_variance'

# ─── DQ Runner Tests ─────────────────────────────────────────────────────────

class TestDQRunner:
    """Tests for dq/run_checks.py"""

    def test_runner_exists(self):
        assert os.path.exists(os.path.join(DQ_DIR, 'run_checks.py'))

    def test_runner_parses(self):
        path = os.path.join(DQ_DIR, 'run_checks.py')
        with open(path) as f:
            content = f.read()
        ast.parse(content)

    def test_runner_has_default_checks(self):
        path = os.path.join(DQ_DIR, 'run_checks.py')
        with open(path) as f:
            content = f.read()
        assert "DEFAULT_CHECKS" in content
        assert "null_rate" in content
        assert "orphan_rate" in content
        assert "row_count_variance" in content

    def test_runner_has_quarantine_logic(self):
        path = os.path.join(DQ_DIR, 'run_checks.py')
        with open(path) as f:
            content = f.read()
        assert "quarantine" in content.lower()
        assert "INSERT INTO silver.quarantine" in content

    def test_runner_has_logging(self):
        path = os.path.join(DQ_DIR, 'run_checks.py')
        with open(path) as f:
            content = f.read()
        assert "data_quality_log" in content
        assert "INSERT INTO silver.data_quality_log" in content

    def test_runner_has_main_function(self):
        path = os.path.join(DQ_DIR, 'run_checks.py')
        with open(path) as f:
            content = f.read()
        assert "def main" in content
        assert "if __name__" in content

# ─── Freshness Monitor Tests ──────────────────────────────────────────────────

class TestFreshnessMonitor:
    """Tests for scripts/freshness.py"""

    def test_freshness_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, 'freshness.py'))

    def test_freshness_parses(self):
        path = os.path.join(SCRIPTS_DIR, 'freshness.py')
        with open(path) as f:
            content = f.read()
        ast.parse(content)

    def test_freshness_has_sla_check(self):
        path = os.path.join(SCRIPTS_DIR, 'freshness.py')
        with open(path) as f:
            content = f.read()
        assert "sla_hours" in content
        assert "sla_boundary" in content or "timedelta" in content

    def test_freshness_checks_all_tables(self):
        path = os.path.join(SCRIPTS_DIR, 'freshness.py')
        with open(path) as f:
            content = f.read()
        assert "title_basics" in content
        assert "name_basics" in content
        assert "title_rating" in content

    def test_freshness_has_main(self):
        path = os.path.join(SCRIPTS_DIR, 'freshness.py')
        with open(path) as f:
            content = f.read()
        assert "def main" in content
        assert "if __name__" in content

# ─── Neo4j Sync Tests ────────────────────────────────────────────────────────

class TestNeo4jSync:
    """Tests for scripts/neo4j_sync.py"""

    def test_neo4j_sync_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, 'neo4j_sync.py'))

    def test_neo4j_sync_parses(self):
        path = os.path.join(SCRIPTS_DIR, 'neo4j_sync.py')
        with open(path) as f:
            content = f.read()
        ast.parse(content)

    def test_neo4j_sync_has_cypher_schema(self):
        path = os.path.join(SCRIPTS_DIR, 'neo4j_sync.py')
        with open(path) as f:
            content = f.read()
        assert "CYPHER_SCHEMA" in content
        assert "CREATE CONSTRAINT" in content
        assert "CREATE INDEX" in content

    def test_neo4j_sync_has_merge_queries(self):
        path = os.path.join(SCRIPTS_DIR, 'neo4j_sync.py')
        with open(path) as f:
            content = f.read()
        assert "MERGE" in content
        assert "UNWIND" in content

    def test_neo4j_sync_has_relationships(self):
        path = os.path.join(SCRIPTS_DIR, 'neo4j_sync.py')
        with open(path) as f:
            content = f.read()
        assert "ACTED_IN" in content
        assert ":Title" in content
        assert ":Person" in content

    def test_neo4j_sync_has_main(self):
        path = os.path.join(SCRIPTS_DIR, 'neo4j_sync.py')
        with open(path) as f:
            content = f.read()
        assert "def main" in content
        assert "if __name__" in content

# ─── ETL Runner Tests ────────────────────────────────────────────────────────

class TestETLRunner:
    """Tests for scripts/etl_runner.py"""

    def test_etl_runner_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, 'etl_runner.py'))

    def test_etl_runner_parses(self):
        path = os.path.join(SCRIPTS_DIR, 'etl_runner.py')
        with open(path) as f:
            content = f.read()
        ast.parse(content)

    def test_etl_runner_has_read_bronze(self):
        path = os.path.join(SCRIPTS_DIR, 'etl_runner.py')
        with open(path) as f:
            content = f.read()
        assert "def read_bronze" in content
        assert "def upsert_to_silver" in content
        assert "def main" in content

    def test_etl_runner_uses_transforms(self):
        path = os.path.join(SCRIPTS_DIR, 'etl_runner.py')
        with open(path) as f:
            content = f.read()
        assert "from silver.transform import" in content
        assert "from silver.upsert import" in content
        assert "from silver.fk_checks import" in content

    def test_etl_runner_has_argparse(self):
        path = os.path.join(SCRIPTS_DIR, 'etl_runner.py')
        with open(path) as f:
            content = f.read()
        assert "argparse" in content
        assert "--bronze-path" in content
        assert "--jdbc-url" in content

# ─── Performance Benchmarks ───────────────────────────────────────────────────

class TestDQPerformance:
    """Performance benchmarks for DQ framework"""

    def test_config_parse_time(self):
        """Benchmark: DQ config should parse in <50ms"""
        path = os.path.join(DQ_DIR, 'config.yaml')
        start = time.perf_counter()
        for _ in range(100):
            with open(path) as f:
                yaml.safe_load(f)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 50, f"Config parse avg {avg_ms:.1f}ms > 50ms threshold"

    def test_runner_parse_time(self):
        """Benchmark: DQ runner should parse in <100ms"""
        path = os.path.join(DQ_DIR, 'run_checks.py')
        start = time.perf_counter()
        for _ in range(100):
            with open(path) as f:
                ast.parse(f.read())
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 100, f"Runner parse avg {avg_ms:.1f}ms > 100ms threshold"

