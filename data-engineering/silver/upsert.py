# DEPRECATED — use inline SCD2 merge in silver_operator.py (lines 331-416)
# This module contained PySpark-based upsert logic (SILVER_TABLE_DDL,
# generate_merge_sql) that is no longer used since the pipeline migrated
# to DuckDB + psycopg2 COPY.
#
# All table definitions and merge SQL are now handled inline in
# SilverTransformOperator.execute() via:
#   - table_defs (line 184)
#   - scd2_pk_map (line 331)
#   - Inline SCD2 UPDATE + INSERT (lines 374-415)
#
# Retained as reference for future DuckDB-native upsert implementations.
