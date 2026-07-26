# DEPRECATED — use inline SCD2 in silver_operator.py (lines 331-416)
# This module contained PySpark-based SCD2 logic that is no longer used
# since the pipeline migrated to DuckDB + psycopg2 COPY.
# All SCD2 merge logic (expire old, insert new) is now handled directly
# in SilverTransformOperator.execute() via PostgreSQL UPDATE/INSERT.
# 
# Functions removed:
#   - generate_scd2_columns()     — PySpark DataFrame-based
#   - compute_scd2_close_sql()    — superseded by inline SQL in silver_operator.py
#   - build_scd2_merge_sql()      — superseded by inline SQL in silver_operator.py
# 
# Retained as reference for future DuckDB-native SCD2 implementation (T3.3).
