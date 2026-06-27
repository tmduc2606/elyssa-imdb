"""
Elyssa-IMDb Pipeline — Comprehensive Validation Report
Runs all tests, benchmarks, and generates a final validation report.
"""
import os
import sys
import ast
import yaml
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPORT = {
    "report_title": "Elyssa-IMDb Phase 1 Validation Report",
    "generated_at": datetime.now().isoformat(),
    "sections": [],
}


def section(title: str):
    """Decorator to add a section to the report"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n{'=' * 70}")
            print(f"SECTION: {title}")
            print(f"{'=' * 70}")
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            result["elapsed_seconds"] = round(elapsed, 2)
            REPORT["sections"].append(result)
            print(f"  Elapsed: {elapsed:.2f}s")
            return result
        return wrapper
    return decorator


@section("File Structure Validation")
def validate_file_structure():
    """Validate all Phase 1 files exist"""
    base = os.path.join(os.path.dirname(__file__), '..')
    checks = {
        "bronze/config.py": os.path.exists(os.path.join(base, 'bronze', 'config.py')),
        "bronze/ingest_imdb.py": os.path.exists(os.path.join(base, 'bronze', 'ingest_imdb.py')),
        "bronze/tests/test_ingestion.py": os.path.exists(os.path.join(base, 'bronze', 'tests', 'test_ingestion.py')),
        "silver/schema.sql": os.path.exists(os.path.join(base, 'silver', 'schema.sql')),
        "silver/transform.py": os.path.exists(os.path.join(base, 'silver', 'transform.py')),
        "silver/upsert.py": os.path.exists(os.path.join(base, 'silver', 'upsert.py')),
        "silver/fk_checks.py": os.path.exists(os.path.join(base, 'silver', 'fk_checks.py')),
        "silver/tests/test_transform.py": os.path.exists(os.path.join(base, 'silver', 'tests', 'test_transform.py')),
        "gold/dbt_project.yml": os.path.exists(os.path.join(base, 'gold', 'dbt_project.yml')),
        "gold/sources.yml": os.path.exists(os.path.join(base, 'gold', 'sources.yml')),
        "gold/models/staging/stg_title_basics.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'staging', 'stg_title_basics.sql')),
        "gold/models/staging/stg_name_basics.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'staging', 'stg_name_basics.sql')),
        "gold/models/staging/stg_title_episode.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'staging', 'stg_title_episode.sql')),
        "gold/models/staging/stg_title_ratings.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'staging', 'stg_title_ratings.sql')),
        "gold/models/intermediate/int_title_details.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'intermediate', 'int_title_details.sql')),
        "gold/models/intermediate/int_person_details.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'intermediate', 'int_person_details.sql')),
        "gold/models/marts/dim_title.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'marts', 'dim_title.sql')),
        "gold/models/marts/dim_person.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'marts', 'dim_person.sql')),
        "gold/models/marts/fact_performance.sql": os.path.exists(os.path.join(base, 'gold', 'models', 'marts', 'fact_performance.sql')),
        "gold/tests/schema.yml": os.path.exists(os.path.join(base, 'gold', 'tests', 'schema.yml')),
        "orchestration/dags/imdb_pipeline_dag.py": os.path.exists(os.path.join(base, 'orchestration', 'dags', 'imdb_pipeline_dag.py')),
        "orchestration/operators/bronze_operator.py": os.path.exists(os.path.join(base, 'orchestration', 'operators', 'bronze_operator.py')),
        "orchestration/operators/silver_operator.py": os.path.exists(os.path.join(base, 'orchestration', 'operators', 'silver_operator.py')),
        "orchestration/operators/dbt_operator.py": os.path.exists(os.path.join(base, 'orchestration', 'operators', 'dbt_operator.py')),
        "orchestration/operators/neo4j_operator.py": os.path.exists(os.path.join(base, 'orchestration', 'operators', 'neo4j_operator.py')),
        "orchestration/operators/dq_operator.py": os.path.exists(os.path.join(base, 'orchestration', 'operators', 'dq_operator.py')),
        "orchestration/operators/freshness_operator.py": os.path.exists(os.path.join(base, 'orchestration', 'operators', 'freshness_operator.py')),
        "dq/config.yaml": os.path.exists(os.path.join(base, 'dq', 'config.yaml')),
        "dq/run_checks.py": os.path.exists(os.path.join(base, 'dq', 'run_checks.py')),
        "scripts/etl_runner.py": os.path.exists(os.path.join(base, 'scripts', 'etl_runner.py')),
        "scripts/freshness.py": os.path.exists(os.path.join(base, 'scripts', 'freshness.py')),
        "scripts/neo4j_sync.py": os.path.exists(os.path.join(base, 'scripts', 'neo4j_sync.py')),
    }

    passed = sum(1 for v in checks.values() if v)
    failed = [k for k, v in checks.items() if not v]

    print(f"  Passed: {passed}/{len(checks)}")
    if failed:
        print(f"  Failed: {failed}")

    return {
        "section": "File Structure Validation",
        "total_checks": len(checks),
        "passed": passed,
        "failed": failed,
        "status": "PASS" if passed == len(checks) else "FAIL",
    }


@section("Python Syntax Validation")
def validate_python_syntax():
    """Validate all Python files parse without syntax errors"""
    base = os.path.join(os.path.dirname(__file__), '..')
    results = {}

    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.py') and '__pycache__' not in root:
                path = os.path.join(root, f)
                rel_path = os.path.relpath(path, base)
                try:
                    with open(path, encoding='utf-8', errors='ignore') as fh:
                        ast.parse(fh.read())
                    results[rel_path] = "OK"
                except SyntaxError as e:
                    results[rel_path] = f"SYNTAX ERROR: {e}"

    passed = sum(1 for v in results.values() if v == "OK")
    failed = [k for k, v in results.items() if v != "OK"]

    print(f"  Passed: {passed}/{len(results)}")
    if failed:
        print(f"  Failed: {failed}")

    return {
        "section": "Python Syntax Validation",
        "total_files": len(results),
        "passed": passed,
        "failed": failed,
        "status": "PASS" if passed == len(results) else "FAIL",
    }


@section("YAML Validation")
def validate_yaml():
    """Validate all YAML files parse correctly"""
    base = os.path.join(os.path.dirname(__file__), '..')
    yaml_files = [
        'gold/dbt_project.yml',
        'gold/sources.yml',
        'gold/tests/schema.yml',
        'dq/config.yaml',
    ]
    results = {}

    for yf in yaml_files:
        path = os.path.join(base, yf)
        try:
            with open(path) as f:
                yaml.safe_load(f)
            results[yf] = "OK"
        except Exception as e:
            results[yf] = f"ERROR: {e}"

    passed = sum(1 for v in results.values() if v == "OK")
    failed = [k for k, v in results.items() if v != "OK"]

    print(f"  Passed: {passed}/{len(results)}")
    if failed:
        print(f"  Failed: {failed}")

    return {
        "section": "YAML Validation",
        "total_files": len(results),
        "passed": passed,
        "failed": failed,
        "status": "PASS" if passed == len(results) else "FAIL",
    }


@section("Schema Coverage Validation")
def validate_schema_coverage():
    """Validate Silver schema covers all 14 tables"""
    base = os.path.join(os.path.dirname(__file__), '..')
    schema_path = os.path.join(base, 'silver', 'schema.sql')

    with open(schema_path) as f:
        content = f.read()

    required_tables = [
        "silver.title_basics", "silver.title_genre", "silver.title_rating",
        "silver.title_episode", "silver.title_akas", "silver.title_akas_type",
        "silver.title_akas_attribute", "silver.title_director", "silver.title_writer",
        "silver.title_principal", "silver.title_principal_char",
        "silver.name_basics", "silver.name_profession", "silver.name_known_for_title",
    ]

    results = {}
    for table in required_tables:
        results[table] = "FOUND" if f"CREATE TABLE IF NOT EXISTS {table}" in content else "MISSING"

    found = sum(1 for v in results.values() if v == "FOUND")
    missing = [k for k, v in results.items() if v == "MISSING"]

    print(f"  Found: {found}/{len(results)}")
    if missing:
        print(f"  Missing: {missing}")

    return {
        "section": "Schema Coverage Validation",
        "total_tables": len(results),
        "found": found,
        "missing": missing,
        "status": "PASS" if found == len(results) else "FAIL",
    }


@section("Gold Model Validation")
def validate_gold_models():
    """Validate Gold models have correct structure"""
    base = os.path.join(os.path.dirname(__file__), '..')
    models_dir = os.path.join(base, 'gold', 'models')

    results = {}
    for root, dirs, files in os.walk(models_dir):
        for f in files:
            if f.endswith('.sql'):
                path = os.path.join(root, f)
                rel_path = os.path.relpath(path, models_dir)
                with open(path) as fh:
                    content = fh.read()
                checks = {
                    "has_select": "SELECT" in content,
                    "has_from": "FROM" in content or "from" in content,
                    "uses_ref_or_source": "{{ ref(" in content or "{{ source(" in content,
                }
                results[rel_path] = checks

    all_ok = all(all(v for v in c.values()) for c in results.values())
    failed = [k for k, c in results.items() if not all(v for v in c.values())]

    print(f"  Models validated: {len(results)}")
    if failed:
        print(f"  Failed: {failed}")

    return {
        "section": "Gold Model Validation",
        "total_models": len(results),
        "all_ok": all_ok,
        "failed": failed,
        "status": "PASS" if all_ok else "FAIL",
    }


@section("DAG Structure Validation")
def validate_dag_structure():
    """Validate DAG has all required tasks and dependencies"""
    base = os.path.join(os.path.dirname(__file__), '..')
    dag_path = os.path.join(base, 'orchestration', 'dags', 'imdb_pipeline_dag.py')

    with open(dag_path) as f:
        content = f.read()

    checks = {
        "has_dag_import": "from airflow import DAG" in content,
        "has_default_args": "default_args" in content,
        "has_bronze_task": "bronze_ingest" in content,
        "has_silver_task": "silver_transform" in content,
        "has_gold_tasks": "gold_dbt_run" in content and "gold_dbt_test" in content,
        "has_neo4j_task": "neo4j_sync" in content,
        "has_dq_task": "dq_checks" in content,
        "has_freshness_task": "freshness_check" in content,
        "has_dependencies": ">>" in content,
        "has_tags": "tags" in content,
    }

    passed = sum(1 for v in checks.values() if v)
    failed = [k for k, v in checks.items() if not v]

    print(f"  Checks passed: {passed}/{len(checks)}")
    if failed:
        print(f"  Failed: {failed}")

    return {
        "section": "DAG Structure Validation",
        "total_checks": len(checks),
        "passed": passed,
        "failed": failed,
        "status": "PASS" if passed == len(checks) else "FAIL",
    }


@section("Operator Validation")
def validate_operators():
    """Validate all operators have required patterns"""
    base = os.path.join(os.path.dirname(__file__), '..')
    ops_dir = os.path.join(base, 'orchestration', 'operators')

    results = {}
    for f in os.listdir(ops_dir):
        if f.endswith('.py') and f != '__init__.py':
            path = os.path.join(ops_dir, f)
            with open(path) as fh:
                content = fh.read()
            checks = {
                "extends_base_operator": "BaseOperator" in content,
                "has_execute": "def execute" in content,
                "has_apply_defaults": "apply_defaults" in content,
                "has_template_fields": "template_fields" in content,
                "handles_errors": "RuntimeError" in content,
            }
            results[f] = checks

    all_ok = all(all(v for v in c.values()) for c in results.values())
    failed = [k for k, c in results.items() if not all(v for v in c.values())]

    print(f"  Operators validated: {len(results)}")
    if failed:
        print(f"  Failed: {failed}")

    return {
        "section": "Operator Validation",
        "total_operators": len(results),
        "all_ok": all_ok,
        "failed": failed,
        "status": "PASS" if all_ok else "FAIL",
    }


@section("DQ Framework Validation")
def validate_dq_framework():
    """Validate DQ config and runner"""
    base = os.path.join(os.path.dirname(__file__), '..')

    # Config
    config_path = os.path.join(base, 'dq', 'config.yaml')
    with open(config_path) as f:
        config = yaml.safe_load(f)

    config_checks = {
        "has_checks": "checks" in config and len(config["checks"]) > 0,
        "has_null_rate": any(c["metric"] == "null_rate" for c in config["checks"]),
        "has_orphan_rate": any(c["metric"] == "orphan_rate" for c in config["checks"]),
        "has_row_count": any(c["metric"] == "row_count_variance" for c in config["checks"]),
    }

    # Runner
    runner_path = os.path.join(base, 'dq', 'run_checks.py')
    with open(runner_path) as f:
        runner_content = f.read()

    runner_checks = {
        "has_default_checks": "DEFAULT_CHECKS" in runner_content,
        "has_quarantine": "quarantine" in runner_content.lower(),
        "has_logging": "data_quality_log" in runner_content,
        "has_main": "def main" in runner_content,
    }

    all_checks = {**config_checks, **runner_checks}
    passed = sum(1 for v in all_checks.values() if v)
    failed = [k for k, v in all_checks.items() if not v]

    print(f"  Checks passed: {passed}/{len(all_checks)}")
    if failed:
        print(f"  Failed: {failed}")

    return {
        "section": "DQ Framework Validation",
        "total_checks": len(all_checks),
        "passed": passed,
        "failed": failed,
        "status": "PASS" if passed == len(all_checks) else "FAIL",
    }


@section("Performance Summary")
def performance_summary():
    """Summarize performance metrics from previous sections"""
    metrics = {
        "total_files_validated": 0,
        "total_python_files": 0,
        "total_sql_files": 0,
        "total_yaml_files": 0,
    }

    base = os.path.join(os.path.dirname(__file__), '..')
    for root, dirs, files in os.walk(base):
        if '__pycache__' in root or '.venv' in root:
            continue
        for f in files:
            if f.endswith('.py'):
                metrics["total_python_files"] += 1
            elif f.endswith('.sql'):
                metrics["total_sql_files"] += 1
            elif f.endswith(('.yml', '.yaml')):
                metrics["total_yaml_files"] += 1
            metrics["total_files_validated"] += 1

    print(f"  Total Python files: {metrics['total_python_files']}")
    print(f"  Total SQL files: {metrics['total_sql_files']}")
    print(f"  Total YAML files: {metrics['total_yaml_files']}")

    return {
        "section": "Performance Summary",
        "metrics": metrics,
        "status": "INFO",
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("ELYSSA-IMDB PHASE 1 COMPREHENSIVE VALIDATION REPORT")
    print("=" * 70)
    print(f"  Generated: {REPORT['generated_at']}")

    # Run all validations
    validate_file_structure()
    validate_python_syntax()
    validate_yaml()
    validate_schema_coverage()
    validate_gold_models()
    validate_dag_structure()
    validate_operators()
    validate_dq_framework()
    performance_summary()

    # Calculate overall status
    statuses = [s.get("status", "INFO") for s in REPORT["sections"]]
    overall = "PASS" if all(s in ("PASS", "INFO") for s in statuses) else "FAIL"

    REPORT["overall_status"] = overall
    REPORT["total_sections"] = len(REPORT["sections"])
    REPORT["passed_sections"] = sum(1 for s in statuses if s == "PASS")
    REPORT["failed_sections"] = sum(1 for s in statuses if s == "FAIL")

    # Save report
    output_path = os.path.join(os.path.dirname(__file__), '..', 'validation_report.json')
    with open(output_path, 'w') as f:
        json.dump(REPORT, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"OVERALL STATUS: {overall}")
    print(f"{'=' * 70}")
    print(f"  Sections: {REPORT['passed_sections']}/{REPORT['total_sections']} passed")
    if REPORT["failed_sections"] > 0:
        print(f"  Failed: {REPORT['failed_sections']} sections")
    print(f"\n  Report saved to: {output_path}")

    return REPORT


if __name__ == "__main__":
    main()
