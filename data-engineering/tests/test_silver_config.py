"""Silver layer configuration tests — schema.sql, FK checks, contracts."""

import os
from unittest.mock import MagicMock

from silver.fk_checks import FK_CHECKS, run_fk_checks
from silver.contract_validator import (
    ContractValidator, validate_silver_to_gold,
)

SILVER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "silver")


def _schema_sql() -> str:
    with open(os.path.join(SILVER_DIR, "schema.sql"), encoding="utf-8") as f:
        return f.read()


class TestFkChecks:
    def test_fk_checks_has_all_8_checks(self):
        assert len(FK_CHECKS) == 8

    def test_each_check_has_required_fields(self):
        for check in FK_CHECKS:
            assert "name" in check
            assert "sql" in check
            assert "SELECT" in check["sql"].upper()

    def test_fk_check_names_are_descriptive(self):
        names = [c["name"] for c in FK_CHECKS]
        assert "title_episode_parent_exists" in names
        assert "title_rating_title_exists" in names
        assert "title_director_title_exists" in names
        assert "fact_performance_nconst_exists_in_name_basics" in names

    def test_fk_check_thresholds_are_numeric(self):
        for check in FK_CHECKS:
            assert isinstance(check["threshold"], (int, float))
            assert check["threshold"] >= 0

    def test_run_fk_checks_all_pass(self):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)
        conn.cursor.return_value = cursor
        results, all_passed = run_fk_checks(conn)
        assert all_passed is True
        assert len(results) == len(FK_CHECKS)
        assert all(r["passed"] for r in results)

    def test_run_fk_checks_detects_orphans(self):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(0,)] * 7 + [(5,)]
        conn.cursor.return_value = cursor
        results, all_passed = run_fk_checks(conn)
        assert all_passed is False
        failed = [r for r in results if not r["passed"]]
        assert len(failed) == 1
        assert failed[0]["check_name"] == "fact_performance_nconst_exists_in_name_basics"
        assert failed[0]["orphan_count"] == 5


class TestSchemaSql:
    def test_schema_file_exists(self):
        assert os.path.exists(os.path.join(SILVER_DIR, "schema.sql"))

    def test_schema_has_timescaledb(self):
        assert "CREATE EXTENSION IF NOT EXISTS timescaledb" in _schema_sql()

    def test_schema_has_14_tables(self):
        tables = [
            "silver.title_basics", "silver.title_genre", "silver.title_rating",
            "silver.title_episode", "silver.title_akas", "silver.title_akas_type",
            "silver.title_akas_attribute", "silver.title_director", "silver.title_writer",
            "silver.title_principal", "silver.title_principal_char",
            "silver.name_basics", "silver.name_profession", "silver.name_known_for_title",
        ]
        content = _schema_sql()
        for table in tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in content, f"Table {table} not found"

    def test_schema_has_scd2_columns(self):
        content = _schema_sql()
        assert "valid_from" in content
        assert "valid_to" in content
        assert "is_current" in content

    def test_schema_has_surrogate_keys(self):
        content = _schema_sql()
        assert "CREATE SEQUENCE IF NOT EXISTS silver.title_key_seq" in content
        assert "CREATE SEQUENCE IF NOT EXISTS silver.name_key_seq" in content
        assert "CREATE SEQUENCE IF NOT EXISTS silver.character_key_seq" in content

    def test_schema_has_governance_tables(self):
        content = _schema_sql()
        assert "silver.graph_sync_status" in content
        assert "silver.data_quality_log" in content
        assert "silver.quarantine" in content


class TestContractValidator:
    def test_validate_column_presence(self):
        validator = ContractValidator.__new__(ContractValidator)
        validator.contract = {"required_columns": ["a", "b"]}
        missing = validator.validate_column_presence(["a", "c"], ["a", "b"])
        assert missing == ["b"]

    def test_validate_null_constraints(self):
        validator = ContractValidator.__new__(ContractValidator)
        validator.contract = {"not_null_columns": ["a"]}
        violations = validator.validate_null_constraints({"a": 0.02, "b": 0.0}, ["a"])
        assert violations == {"a": 0.02}

    def test_validate_fk_integrity(self):
        validator = ContractValidator.__new__(ContractValidator)
        validator.contract = {}
        violations = validator.validate_fk_integrity({"t": 3}, max_orphans=1)
        assert violations == {"t": 3}

    def test_validate_row_count(self):
        validator = ContractValidator.__new__(ContractValidator)
        validator.contract = {}
        assert validator.validate_row_count(10, min_count=5) is True
        assert validator.validate_row_count(4, min_count=5) is False

    def test_run_full_validation_pass(self):
        validator = ContractValidator.__new__(ContractValidator)
        validator.contract = {
            "required_columns": ["tconst", "title_type"],
            "not_null_columns": ["tconst"],
            "min_row_count": 10,
        }
        report = validator.run_full_validation(
            ["tconst", "title_type"], {"tconst": 0.0}, {"episode": 0}, 100)
        assert report["passed"] is True
        assert report["violations"] == []

    def test_run_full_validation_fail_missing_columns(self):
        validator = ContractValidator.__new__(ContractValidator)
        validator.contract = {"required_columns": ["tconst", "title_type"]}
        report = validator.run_full_validation(
            ["tconst"], {"tconst": 0.0}, {}, 100)
        assert report["passed"] is False
        assert report["violations"][0]["type"] == "missing_columns"

    def test_validate_silver_to_gold(self):
        report = validate_silver_to_gold(
            ["tconst", "title_type", "primary_title"],
            {"tconst": 0.0, "title_type": 0.0, "primary_title": 0.0},
            {},
            200000,
        )
        assert report["passed"] is True
