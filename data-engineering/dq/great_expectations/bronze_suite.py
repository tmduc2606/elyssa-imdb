"""
Great Expectations Validation Suite — PostgreSQL backend.

Validates Silver PostgreSQL tables for data quality:
- Row count > 0
- Column null rate thresholds

Uses GX 1.18 PostgreSQL data source.
"""

import os
import sys
from typing import Optional

import great_expectations.expectations as gxe
from great_expectations.data_context import get_context
from great_expectations.core.expectation_suite import ExpectationSuite
from great_expectations.core.validation_definition import ValidationDefinition
from great_expectations.checkpoint.checkpoint import Checkpoint


SILVER_TABLES = [
    {
        "name": "title_basics",
        "table": "silver.title_basics",
        "null_threshold": {"primary_title": 0.0, "title_type": 0.0},
    },
    {
        "name": "name_basics",
        "table": "silver.name_basics",
        "null_threshold": {"primary_name": 0.0},
    },
    {
        "name": "title_episode",
        "table": "silver.title_episode",
        "null_threshold": {"parent_tconst": 0.01},
    },
    {
        "name": "title_rating",
        "table": "silver.title_rating",
        "null_threshold": {"average_rating": 0.5, "num_votes": 0.5},
    },
    {
        "name": "title_principal_char",
        "table": "silver.title_principal_char",
        "null_threshold": {"character_name": 0.0},
    },
]

DS_NAME = "silver_postgres"
CONN_STRING = "postgresql://elyssa:elyssa_pg_2026@postgres:5432/elyssa_warehouse"


def build_suite(name: str, null_threshold: dict) -> ExpectationSuite:
    suite = ExpectationSuite(name=f"silver_{name}_suite")
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=1))
    for col, threshold in null_threshold.items():
        suite.add_expectation(
            gxe.ExpectColumnValuesToNotBeNull(column=col, mostly=(1.0 - threshold))
        )
    return suite


def _get_datasource(context):
    try:
        return context.data_sources.get(DS_NAME)
    except KeyError:
        return context.data_sources.add_or_update_sql(
            name=DS_NAME,
            connection_string=CONN_STRING,
        )


def validate_silver(
    table_name: str,
    full_table: str,
    null_threshold: dict,
) -> dict:
    context = get_context()
    ds = _get_datasource(context)

    suite = build_suite(table_name, null_threshold)
    context.suites.add(suite)

    asset = ds.add_table_asset(name=f"asset_{table_name}", table_name=full_table)
    batch_def = asset.add_batch_definition(name=f"batch_{table_name}")

    val_def = ValidationDefinition(
        name=f"val_{table_name}",
        data=batch_def,
        suite=suite,
    )
    context.validation_definitions.add(val_def)

    checkpoint = Checkpoint(
        name=f"ck_{table_name}",
        validation_definitions=[val_def],
        actions=[],
    )
    context.checkpoints.add(checkpoint)

    result = checkpoint.run()
    expectations = []
    for val_result_id, val_result in result.run_results.items():
        for r in val_result.results:
            expectations.append({
                "success": r.success,
                "expectation_type": r.expectation_config.type,
            })
    return {
        "success": result.success,
        "results": expectations,
    }


def validate_all() -> list[dict]:
    results = []
    for tbl in SILVER_TABLES:
        print(f"[GX] Validating {tbl['table']}...")
        try:
            result = validate_silver(tbl["name"], tbl["table"], tbl["null_threshold"])
            success = result["success"]
            results.append({"table": tbl["table"], "success": success, "result": result})
            print(f"[GX] {'PASS' if success else 'FAIL'} {tbl['table']}")
            if not success:
                for r in result.get("results", []):
                    if not r["success"]:
                        print(f"  - {r['expectation_type']}: FAILED")
        except Exception as e:
            print(f"[GX] ERROR {tbl['table']}: {e}")
            results.append({"table": tbl["table"], "success": False, "error": str(e)})
    return results


if __name__ == "__main__":
    # bronze_path arg is accepted for API compatibility with DataQualityOperator
    # but this suite validates Silver PostgreSQL tables (post-ingestion)
    if len(sys.argv) > 1 and sys.argv[1].startswith("/"):
        print(f"[GX] Note: bronze_path={sys.argv[1]} ignored — validating Silver tables")
    results = validate_all()
    all_ok = all(r["success"] for r in results)
    print(f"[GX] {'All passed' if all_ok else 'Some checks failed'}")
    sys.exit(0 if all_ok else 1)
