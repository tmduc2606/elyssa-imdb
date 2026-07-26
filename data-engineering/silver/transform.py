# DEPRECATED — all transforms use DuckDB SQL via silver_operator.py
# This module contained PySpark-based transform logic (ARRAY_FIELDS,
# TYPE_MAP, null_to_empty, rename_to_silver, explode_array) that is
# no longer used since the pipeline migrated to DuckDB + psycopg2 COPY.
#
# Column mapping, type coercion, array explosion, and NOT NULL fixes are
# now handled inline in SilverTransformOperator.execute() via:
#   - camel_to_snake_map (line 218)
#   - not_null_fixes (line 253)
#   - bool_casts (line 259)
#   - not_null_filters (line 265)
#   - child_table_defs (line 447)
#
# Retained as reference for future DuckDB-native implementations.
