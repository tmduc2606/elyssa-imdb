"""Orchestration validation tests — DAG structure and operators."""

import ast
import os

ORCH_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "orchestration")
DAGS_DIR = os.path.join(ORCH_DIR, "dags")
OPERATORS_DIR = os.path.join(ORCH_DIR, "operators")

DAG_PATH = os.path.join(DAGS_DIR, "imdb_pipeline_dag.py")


def _dag_content() -> str:
    with open(DAG_PATH, encoding="utf-8") as f:
        return f.read()


class TestDAGStructure:
    def test_dag_file_exists(self):
        assert os.path.exists(DAG_PATH)

    def test_dag_file_parses(self):
        ast.parse(_dag_content())

    def test_dag_has_required_imports(self):
        content = _dag_content()
        assert "from airflow import DAG" in content
        assert "EmptyOperator" in content
        assert "PythonOperator" in content

    def test_dag_has_default_args(self):
        content = _dag_content()
        assert "default_args" in content
        assert "retries" in content
        assert "retry_delay" in content
        assert "email_on_failure" in content

    def test_dag_has_correct_schedule(self):
        assert "schedule_interval" in _dag_content() or "schedule" in _dag_content()

    def test_dag_has_tags(self):
        assert "tags" in _dag_content()

    def test_dag_has_pipeline_tasks(self):
        content = _dag_content()
        for task in ["run_bronze", "bronze_ingestion_done", "silver_transform",
                     "gold_dbt_run", "gold_dbt_test", "dq_checks", "freshness_check",
                     "gold_export"]:
            assert task in content, f"task {task} missing from DAG"

    def test_dag_has_task_dependencies(self):
        assert ">>" in _dag_content()


class TestOperators:
    def test_operators_dir_exists(self):
        assert os.path.isdir(OPERATORS_DIR)

    def test_operators_init_exists(self):
        assert os.path.exists(os.path.join(OPERATORS_DIR, "__init__.py"))

    def test_all_operators_exist(self):
        expected = [
            "silver_operator.py", "dbt_operator.py", "dq_operator.py",
            "freshness_operator.py", "imdb_sensor.py", "bronze_sensor.py",
            "dbt_done_sensor.py", "silver_export_operator.py",
            "silver_export_sensor.py", "gold_export_operator.py",
            "gold_export_sensor.py",
        ]
        for op in expected:
            path = os.path.join(OPERATORS_DIR, op)
            assert os.path.exists(path), f"Operator {op} not found"

    def test_operators_parse(self):
        for op_file in os.listdir(OPERATORS_DIR):
            if op_file.endswith(".py") and op_file != "__init__.py":
                with open(os.path.join(OPERATORS_DIR, op_file), encoding="utf-8") as f:
                    ast.parse(f.read())

    def test_execute_operators_import_base_operator(self):
        for op_file in ["silver_operator.py", "dbt_operator.py", "dq_operator.py",
                        "freshness_operator.py", "silver_export_operator.py",
                        "gold_export_operator.py"]:
            with open(os.path.join(OPERATORS_DIR, op_file), encoding="utf-8") as f:
                content = f.read()
            assert "BaseOperator" in content, f"{op_file} doesn't import BaseOperator"

    def test_execute_operators_have_execute_method(self):
        for op_file in ["silver_operator.py", "dbt_operator.py", "dq_operator.py",
                        "freshness_operator.py", "silver_export_operator.py",
                        "gold_export_operator.py"]:
            with open(os.path.join(OPERATORS_DIR, op_file), encoding="utf-8") as f:
                content = f.read()
            assert "def execute" in content, f"{op_file} missing execute method"

    def test_sensors_have_poke_method(self):
        for op_file in ["imdb_sensor.py", "bronze_sensor.py", "dbt_done_sensor.py",
                        "silver_export_sensor.py", "gold_export_sensor.py"]:
            with open(os.path.join(OPERATORS_DIR, op_file), encoding="utf-8") as f:
                content = f.read()
            assert "def poke" in content, f"{op_file} missing poke method"

    def test_operators_have_template_fields(self):
        for op_file in os.listdir(OPERATORS_DIR):
            if op_file.endswith(".py") and op_file != "__init__.py":
                with open(os.path.join(OPERATORS_DIR, op_file), encoding="utf-8") as f:
                    content = f.read()
                assert "template_fields" in content, f"{op_file} missing template_fields"

    def test_operators_have_apply_defaults(self):
        """Airflow 3.x: apply_defaults is automatic; verify super().__init__ is called."""
        for op_file in os.listdir(OPERATORS_DIR):
            if op_file.endswith(".py") and op_file != "__init__.py":
                with open(os.path.join(OPERATORS_DIR, op_file), encoding="utf-8") as f:
                    content = f.read()
                assert "super().__init__" in content or "apply_defaults" in content, \
                    f"{op_file} missing super().__init__ or apply_defaults"

    def test_operators_handle_errors(self):
        for op_file in ["silver_operator.py", "dbt_operator.py", "dq_operator.py"]:
            with open(os.path.join(OPERATORS_DIR, op_file), encoding="utf-8") as f:
                content = f.read()
            assert "RuntimeError" in content, f"{op_file} doesn't raise RuntimeError"


class TestSecrets:
    def test_pg_password_raises_without_env(self, monkeypatch):
        import orchestration.config.secrets as secrets
        for key in ("ELYSSA_PG_PASSWORD", "POSTGRES_PASSWORD",
                    "GOLD_EXPORT_PG_PASSWORD"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(secrets, "_get_airflow_connection", lambda: {})
        try:
            secrets.pg_password()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    def test_pg_password_from_env(self, monkeypatch):
        import orchestration.config.secrets as secrets
        monkeypatch.setenv("ELYSSA_PG_PASSWORD", "dummy-pass")
        assert secrets.pg_password() == "dummy-pass"

    def test_pg_connect_kwargs_from_env(self, monkeypatch):
        import orchestration.config.secrets as secrets
        monkeypatch.setenv("ELYSSA_PG_PASSWORD", "dummy-pass")
        monkeypatch.setenv("ELYSSA_PG_HOST", "db")
        monkeypatch.setenv("ELYSSA_PG_PORT", "5433")
        monkeypatch.setenv("ELYSSA_PG_USER", "u")
        monkeypatch.setenv("ELYSSA_PG_DB", "d")
        kwargs = secrets.pg_connect_kwargs()
        assert kwargs["password"] == "dummy-pass"
        assert kwargs["host"] == "db"
        assert kwargs["port"] == 5433

    def test_s3_secret_key_raises_without_env(self, monkeypatch):
        import orchestration.config.secrets as secrets
        monkeypatch.delenv("S3_SECRET_KEY", raising=False)
        monkeypatch.delenv("RUSTFS_SECRET_KEY", raising=False)
        try:
            secrets.s3_secret_key()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    def test_s3_secret_key_from_env(self, monkeypatch):
        import orchestration.config.secrets as secrets
        monkeypatch.setenv("S3_SECRET_KEY", "dummy-key")
        assert secrets.s3_secret_key() == "dummy-key"
