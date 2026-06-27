"""
Orchestration Validation Tests
Validates: DAG structure, operator definitions, task dependencies, retry policies
"""
import os
import sys
import time
import pytest
import ast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

ORCH_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
DAGS_DIR = os.path.join(ORCH_DIR, 'orchestration', 'dags')
OPERATORS_DIR = os.path.join(ORCH_DIR, 'orchestration', 'operators')

# ─── DAG Structure Tests ──────────────────────────────────────────────────────

class TestDAGStructure:
    """Tests for orchestration/dags/imdb_pipeline_dag.py"""

    def test_dag_file_exists(self):
        assert os.path.exists(os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py'))

    def test_dag_file_parses(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        # Should parse without syntax errors
        ast.parse(content)

    def test_dag_has_required_imports(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "from airflow import DAG" in content
        assert "EmptyOperator" in content
        assert "PythonOperator" in content

    def test_dag_has_default_args(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "default_args" in content
        assert "retries" in content
        assert "retry_delay" in content
        assert "email_on_failure" in content

    def test_dag_has_correct_schedule(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "schedule_interval" in content or "schedule" in content

    def test_dag_has_tags(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "tags" in content

    def test_dag_has_bronze_task(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "bronze_ingest" in content

    def test_dag_has_silver_task(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "silver_transform" in content

    def test_dag_has_gold_tasks(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "gold_dbt_run" in content
        assert "gold_dbt_test" in content

    def test_dag_has_neo4j_task(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "neo4j_sync" in content

    def test_dag_has_dq_task(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "dq_checks" in content

    def test_dag_has_freshness_task(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert "freshness_check" in content

    def test_dag_has_task_dependencies(self):
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        with open(path) as f:
            content = f.read()
        assert ">>" in content

# ─── Operator Tests ───────────────────────────────────────────────────────────

class TestOperators:
    """Tests for orchestration/operators/"""

    def test_operators_dir_exists(self):
        assert os.path.isdir(OPERATORS_DIR)

    def test_operators_init_exists(self):
        assert os.path.exists(os.path.join(OPERATORS_DIR, '__init__.py'))

    def test_all_operators_exist(self):
        expected = [
            'bronze_operator.py',
            'silver_operator.py',
            'dbt_operator.py',
            'neo4j_operator.py',
            'dq_operator.py',
            'freshness_operator.py',
        ]
        for op in expected:
            path = os.path.join(OPERATORS_DIR, op)
            assert os.path.exists(path), f"Operator {op} not found"

    def test_operators_parse(self):
        for op_file in os.listdir(OPERATORS_DIR):
            if op_file.endswith('.py') and op_file != '__init__.py':
                path = os.path.join(OPERATORS_DIR, op_file)
                with open(path) as f:
                    content = f.read()
                ast.parse(content)

    def test_operators_import_base_operator(self):
        for op_file in os.listdir(OPERATORS_DIR):
            if op_file.endswith('.py') and op_file != '__init__.py':
                path = os.path.join(OPERATORS_DIR, op_file)
                with open(path) as f:
                    content = f.read()
                assert "BaseOperator" in content, f"{op_file} doesn't import BaseOperator"

    def test_operators_have_execute_method(self):
        for op_file in os.listdir(OPERATORS_DIR):
            if op_file.endswith('.py') and op_file != '__init__.py':
                path = os.path.join(OPERATORS_DIR, op_file)
                with open(path) as f:
                    content = f.read()
                assert "def execute" in content, f"{op_file} missing execute method"

    def test_operators_have_template_fields(self):
        for op_file in ['bronze_operator.py', 'silver_operator.py', 'dq_operator.py', 'freshness_operator.py']:
            path = os.path.join(OPERATORS_DIR, op_file)
            with open(path) as f:
                content = f.read()
            assert "template_fields" in content, f"{op_file} missing template_fields"

    def test_operators_have_apply_defaults(self):
        """Airflow 3.x: apply_defaults is automatic; verify super().__init__ is called instead."""
        for op_file in os.listdir(OPERATORS_DIR):
            if op_file.endswith('.py') and op_file != '__init__.py':
                path = os.path.join(OPERATORS_DIR, op_file)
                with open(path) as f:
                    content = f.read()
                assert "super().__init__" in content or "apply_defaults" in content, \
                    f"{op_file} missing super().__init__ or apply_defaults"

    def test_operators_handle_errors(self):
        for op_file in ['bronze_operator.py', 'silver_operator.py', 'dbt_operator.py', 'neo4j_operator.py', 'dq_operator.py']:
            path = os.path.join(OPERATORS_DIR, op_file)
            with open(path) as f:
                content = f.read()
            assert "RuntimeError" in content, f"{op_file} doesn't raise RuntimeError on failure"

# ─── Performance Benchmarks ───────────────────────────────────────────────────

class TestOrchestrationPerformance:
    """Performance benchmarks for orchestration layer"""

    def test_dag_parse_time(self):
        """Benchmark: DAG file should parse in <100ms"""
        path = os.path.join(DAGS_DIR, 'imdb_pipeline_dag.py')
        start = time.perf_counter()
        for _ in range(100):
            with open(path) as f:
                content = f.read()
            ast.parse(content)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 100, f"DAG parse avg {avg_ms:.1f}ms > 100ms threshold"

    def test_operators_parse_time(self):
        """Benchmark: All operators should parse in <200ms"""
        start = time.perf_counter()
        for _ in range(100):
            for op_file in os.listdir(OPERATORS_DIR):
                if op_file.endswith('.py'):
                    with open(os.path.join(OPERATORS_DIR, op_file)) as f:
                        content = f.read()
                    ast.parse(content)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 200, f"Operators parse avg {avg_ms:.1f}ms > 200ms threshold"
