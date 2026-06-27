import duckdb
import os

db_path = r"data-engineering/duke/gate0/notebooks/imdb_audit.db"
size = os.path.getsize(db_path)
print(f"File size: {size:,} bytes ({size/1024/1024/1024:.2f} GB)")

conn = duckdb.connect(db_path, read_only=True)

# Try different approaches to list tables
print("\nTrying SHOW TABLES...")
try:
    result = conn.execute("SHOW TABLES").fetchall()
    print(f"SHOW TABLES result: {result}")
except Exception as e:
    print(f"SHOW TABLES failed: {e}")

print("\nTrying SELECT from duckdb_tables()...")
try:
    result = conn.execute("SELECT * FROM duckdb_tables()").fetchall()
    print(f"duckdb_tables result: {result[:5]}...")  # First 5
except Exception as e:
    print(f"duckdb_tables failed: {e}")

print("\nTrying SELECT from duckdb_schemas()...")
try:
    result = conn.execute("SELECT * FROM duckdb_schemas()").fetchall()
    print(f"duckdb_schemas result: {result}")
except Exception as e:
    print(f"duckdb_schemas failed: {e}")

print("\nTrying SELECT from duckdb_views()...")
try:
    result = conn.execute("SELECT * FROM duckdb_views()").fetchall()
    print(f"duckdb_views result: {result}")
except Exception as e:
    print(f"duckdb_views failed: {e}")

print("\nTrying SELECT from duckdb_columns()...")
try:
    result = conn.execute("SELECT * FROM duckdb_columns() LIMIT 10").fetchall()
    print(f"duckdb_columns result: {result}")
except Exception as e:
    print(f"duckdb_columns failed: {e}")

# Try to list all objects in bronze schema
print("\nTrying to list objects in bronze schema...")
try:
    result = conn.execute("SELECT * FROM information_schema.tables WHERE table_schema='bronze'").fetchall()
    print(f"information_schema.tables (bronze): {result}")
except Exception as e:
    print(f"information_schema.tables failed: {e}")

conn.close()
