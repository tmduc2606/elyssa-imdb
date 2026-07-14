"""
SCD2 Transform Module — Standalone SCD2 logic for Silver upserts.

Encapsulates:
- valid_from / valid_to / is_current generation
- Surrogate key assignment via nextval()
- SCD2 column computation for MERGE operations
"""

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col, lit, current_timestamp, when, coalesce, expr, monotonically_increasing_id,
)
from pyspark.sql.types import TimestampType, BooleanType, LongType


def generate_scd2_columns(
    df: DataFrame,
    pk_cols: list[str],
    merge_cols: list[str],
    surrogate_key_seq: str,
    valid_from_col: str = "valid_from",
    valid_to_col: str = "valid_to",
    is_current_col: str = "is_current",
    surrogate_key_col: str = "",
) -> DataFrame:
    """
    Add SCD2 tracking columns to a DataFrame before Silver upsert.

    Args:
        df: Input DataFrame (batch of new data)
        pk_cols: Primary key columns for matching
        merge_cols: Columns to check for changes
        surrogate_key_seq: Sequence name for surrogate keys (e.g., 'silver.title_key_seq')
        valid_from_col: Name of valid_from column
        valid_to_col: Name of valid_to column
        is_current_col: Name of is_current column
        surrogate_key_col: Name of surrogate key column (if empty, no surrogate key added)

    Returns:
        DataFrame with SCD2 columns added
    """
    # Add valid_from as current timestamp
    df = df.withColumn(valid_from_col, current_timestamp())

    # Add valid_to as NULL (open-ended)
    df = df.withColumn(valid_to_col, lit(None).cast(TimestampType()))

    # Add is_current as TRUE
    df = df.withColumn(is_current_col, lit(True).cast(BooleanType()))

    # Add surrogate key if specified
    if surrogate_key_col:
        df = df.withColumn(
            surrogate_key_col,
            expr(f"nextval('{surrogate_key_seq}')")
        )

    return df


def compute_scd2_close_sql(
    target_table: str,
    staging_table: str,
    pk_cols: list[str],
    merge_cols: list[str],
    valid_to_col: str = "valid_to",
    is_current_col: str = "is_current",
) -> str:
    """
    Generate SQL to close outdated SCD2 records (set valid_to and is_current=FALSE).

    This is the UPDATE part of the MERGE that marks old versions as expired.
    """
    join_condition = " AND ".join(
        [f"target.{c} = source.{c}" for c in pk_cols]
    )
    change_condition = " OR ".join(
        [f"target.{c} IS DISTINCT FROM source.{c}" for c in merge_cols]
    )

    sql = f"""
    UPDATE {target_table} AS target
    SET {valid_to_col} = current_timestamp(),
        {is_current_col} = FALSE
    FROM {staging_table} AS source
    WHERE {join_condition}
      AND ({change_condition})
      AND target.{is_current_col} = TRUE
    """
    return sql


def build_scd2_merge_sql(
    target_table: str,
    staging_table: str,
    pk_cols: list[str],
    merge_cols: list[str],
    all_columns: list[str],
    surrogate_key_col: str = "",
    surrogate_key_seq: str = "",
) -> tuple[str, str]:
    """
    Build a complete SCD2 MERGE SQL statement.

    Returns:
        (close_sql, merge_sql) — close old versions, then insert/upsert new
    """
    # Close outdated records
    close_sql = compute_scd2_close_sql(target_table, staging_table, pk_cols, merge_cols)

    # Build MERGE for insert + update
    join_condition = " AND ".join(
        [f"target.{c} = source.{c}" for c in pk_cols]
    )

    if merge_cols:
        change_condition = " OR ".join(
            [f"target.{c} IS DISTINCT FROM source.{c}" for c in merge_cols]
        )
        update_set = ", ".join([f"{c} = source.{c}" for c in merge_cols])

        merge_sql = f"""
        MERGE INTO {target_table} AS target
        USING {staging_table} AS source
        ON {join_condition}
        WHEN MATCHED AND ({change_condition}) THEN
            UPDATE SET {update_set},
                       valid_from = current_timestamp(),
                       valid_to = NULL,
                       is_current = TRUE
        WHEN NOT MATCHED THEN
            INSERT ({', '.join(all_columns)}, valid_from, valid_to, is_current)
            VALUES ({', '.join([f'source.{c}' for c in all_columns])},
                    current_timestamp(), NULL, TRUE)
        """
    else:
        # PK-only table (no merge columns — insert only)
        merge_sql = f"""
        MERGE INTO {target_table} AS target
        USING {staging_table} AS source
        ON {join_condition}
        WHEN NOT MATCHED THEN
            INSERT ({', '.join(all_columns)}, valid_from, valid_to, is_current)
            VALUES ({', '.join([f'source.{c}' for c in all_columns])},
                    current_timestamp(), NULL, TRUE)
        """

    return close_sql, merge_sql
