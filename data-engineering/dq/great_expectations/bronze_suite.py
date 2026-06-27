"""
Great Expectations Bronze Suite for PySpark ingestion.

Validates Bronze Parquet output for:
- Column count matches expected schema
- Null rate below threshold for required fields
- PK uniqueness (tconst, nconst)
- Row count > 0
"""

import os
import sys
from typing import Optional

import great_expectations as gx
from great_expectations.checkpoint import Checkpoint
from great_expectations.datasource.fluent.data_assets.data_asset.fluent_data_asset import (
    FluentDataAsset,
)
import great_expectations.expectations as gxe


# ─── Expected schemas per source ───────────────────────────────────────
BRONZE_SCHEMAS = {
    "title.basics": {
        "columns": ["tconst", "titleType", "primaryTitle", "originalTitle",
                     "isAdult", "startYear", "endYear", "runtimeMinutes", "genres"],
        "pk": "tconst",
        "null_threshold": {
            "primaryTitle": 0.0,
            "titleType": 0.0,
        },
    },
    "title.akas": {
        "columns": ["titleId", "ordering", "title", "region", "language",
                     "types", "attributes", "isOriginalTitle"],
        "pk": "titleId",
        "null_threshold": {
            "title": 0.01,
        },
    },
    "title.ratings": {
        "columns": ["tconst", "averageRating", "numVotes"],
        "pk": "tconst",
        "null_threshold": {
            "averageRating": 0.5,
            "numVotes": 0.5,
        },
    },
    "title.episode": {
        "columns": ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
        "pk": "tconst",
        "null_threshold": {
            "parentTconst": 0.0,
        },
    },
    "name.basics": {
        "columns": ["nconst", "primaryName", "birthYear", "deathYear",
                     "primaryProfession", "knownForTitles"],
        "pk": "nconst",
        "null_threshold": {
            "primaryName": 0.0,
        },
    },
}


def build_suite(
    source_name: str,
    parquet_path: str,
    suite_name: Optional[str] = None,
) -> tuple[gx.ExpectationSuite, str]:
    """Build a Great Expectations suite for a single Bronze Parquet source."""
    suite_name = suite_name or f"bronze_{source_name.replace('.', '_')}_suite"
    schema = BRONZE_SCHEMAS.get(source_name, {})

    suite = gx.ExpectationSuite(name=suite_name)

    # 1. Row count > 0
    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(min_value=1)
    )

    # 2. Column count matches
    expected_columns = schema.get("columns", [])
    if expected_columns:
        suite.add_expectation(
            gxe.ExpectTableColumnsToMatchOrderedList(column_list=expected_columns)
        )

    # 3. PK uniqueness
    pk_col = schema.get("pk")
    if pk_col:
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeUnique(column=pk_col)
        )

    # 4. Null rate thresholds
    for col, threshold in schema.get("null_threshold", {}).items():
        suite.add_expectation(
            gxe.ExpectColumnValuesToNotBeNull(column=col, mostly=(1.0 - threshold))
        )

    return suite, suite_name


def validate_parquet(
    source_name: str,
    parquet_path: str,
    context: Optional[gx.DataContext] = None,
) -> dict:
    """Run Great Expectations validation on a Bronze Parquet file."""
    if context is None:
        context = gx.get_context(mode="file")

    suite, suite_name = build_suite(source_name, parquet_path)
    context.suites.add(suite)

    # Create or get the batch definition
    data_source = context.data_sources.add_or_update_spark_filesystem(
        name=f"bronze_{source_name.replace('.', '_')}",
        base_directory=os.path.dirname(parquet_path),
    )

    batch_definition = data_source.add_batch_definition(
        name=f"batch_{source_name.replace('.', '_')}",
        partitioner=None,
    )

    result = list(
        context.checkpoint(
            name=f"bronze_{source_name.replace('.', '_')}_checkpoint",
            run_name_template="%Y%m%d-%H%M%S",
            batch_definition=batch_definition,
            suite_name=suite_name,
            action_list=[
                {
                    "name": "store_validation_result",
                    "action": {"class_name": "StoreValidationResultAction"},
                },
                {
                    "name": "store_evaluation_params",
                    "action": {"class_name": "StoreEvaluationParametersAction"},
                },
            ],
        ).run()
    )

    validation_result = result[0].to_json_dict() if result else {}
    return validation_result


if __name__ == "__main__":
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else "title.basics"
    path = sys.argv[2] if len(sys.argv) > 2 else "bronze/parquet/title.basics"

    if source not in BRONZE_SCHEMAS:
        print(f"[GE] Unknown source: {source}")
        print(f"[GE] Available: {list(BRONZE_SCHEMAS.keys())}")
        sys.exit(1)

    print(f"[GE] Validating {source} from {path}")
    result = validate_parquet(source, path)
    success = all(
        validation["success"]
        for validation in result.get("results", [])
    )
    if success:
        print(f"[GE] All expectations pass for {source}")
    else:
        print(f"[GE] FAILED expectations for {source}:")
        for validation in result.get("results", []):
            if not validation["success"]:
                print(f"  - {validation['expectation_config']['expectation_type']}: FAILED")
        sys.exit(1)
