import os
import sys
import time
import json
import statistics
import math
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import duckdb

BRONZE_PARQUET_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "duke", "gate0", "bronze")
)

SOURCE_TABLES = [
    "title.basics",
    "title.akas",
    "title.crew",
    "title.episode",
    "title.principals",
    "title.ratings",
    "name.basics",
]

PARQUET_PATHS = {
    name: os.path.join(BRONZE_PARQUET_DIR, f"{name}.parquet")
    for name in SOURCE_TABLES
}

REAL_ROW_COUNTS = {
    "title.akas": 57934300,
    "title.basics": 12593486,
    "title.crew": 12593486,
    "title.episode": 9731563,
    "title.principals": 100109752,
    "title.ratings": 1684492,
    "name.basics": 15432611,
}


def _init_duckdb() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute("SET threads = 4")
    conn.execute("SET memory_limit = '2GB'")
    return conn


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _fmt_duration(seconds: float) -> str:
    if seconds < 0.001:
        return f"{seconds*1_000_000:.1f}µs"
    if seconds < 1:
        return f"{seconds*1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.2f}s"
    return f"{seconds/60:.1f}m"


def _fmt_throughput(rows: int, seconds: float) -> str:
    if seconds <= 0:
        return "N/A"
    rate = rows / seconds
    if rate < 1000:
        return f"{rate:.1f} rows/s"
    return f"{rate/1000:.1f}K rows/s"


def _bench_parquet_read(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    results = []
    print("\n  [1/6] Parquet Read Throughput (Full Scan)")
    print("  -------------------------------------------")
    print(f"  {'Table':20s} {'Size':>8s} {'Rows':>12s}  {'Time':>10s}  {'Throughput':>12s}")

    for table_name in SOURCE_TABLES:
        parquet_path = PARQUET_PATHS[table_name]
        file_size = os.path.getsize(parquet_path)

        times = []
        row_count = 0
        num_cols = 0

        for i in range(3):
            t0 = time.perf_counter()
            rel = conn.execute(f"SELECT COUNT(*) as c FROM read_parquet('{parquet_path}')")
            row = rel.fetchone()
            t1 = time.perf_counter()
            if i == 0:
                row_count = row[0]
            times.append(t1 - t0)

        avg_time = statistics.mean(times)
        results.append({
            "table": table_name,
            "file_size": file_size,
            "file_size_str": _fmt_bytes(file_size),
            "rows": row_count,
            "rows_expected": REAL_ROW_COUNTS.get(table_name, 0),
            "row_match_pct": round(row_count / REAL_ROW_COUNTS.get(table_name, 1) * 100, 2) if table_name in REAL_ROW_COUNTS else None,
            "avg_read_s": round(avg_time, 4),
            "min_read_s": round(min(times), 4),
            "throughput_str": _fmt_throughput(row_count, avg_time),
        })

        print(f"  {table_name:20s} {_fmt_bytes(file_size):>8s}  "
              f"{row_count:>12,}  {_fmt_duration(avg_time):>10s}  "
              f"{_fmt_throughput(row_count, avg_time):>12s}")

    return results


def _bench_column_projection(conn: duckdb.DuckDBPyConnection, results: list[dict]) -> None:
    print("\n  [2/6] Column Projection (SELECT 3 cols)")
    print("  -------------------------------------------")

    for r in results:
        table_name = r["table"]
        parquet_path = PARQUET_PATHS[table_name]
        schema = conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        ).fetchall()
        col_names = [s[0] for s in schema][:3]
        col_list = ", ".join(col_names)

        times = []
        for i in range(3):
            t0 = time.perf_counter()
            conn.execute(f"""
                SELECT {col_list}
                FROM read_parquet('{parquet_path}')
                LIMIT 10000
            """).fetchall()
            t1 = time.perf_counter()
            times.append(t1 - t0)

        avg_time = statistics.mean(times)
        min_time = min(times)
        r["avg_col_project_s"] = round(avg_time, 4)
        print(f"  {table_name:20s} {str(col_names):30s} {_fmt_duration(avg_time):>10s}")


def _bench_aggregation(conn: duckdb.DuckDBPyConnection, results: list[dict]) -> None:
    print("\n  [3/6] Aggregation Benchmarks")
    print("  ----------------------------")

    for r in results:
        table_name = r["table"]
        parquet_path = PARQUET_PATHS[table_name]
        schema = conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        ).fetchall()
        first_col = schema[0][0]

        times = []
        for i in range(3):
            t0 = time.perf_counter()
            conn.execute(f"""
                SELECT COUNT(*), COUNT(DISTINCT "{first_col}")
                FROM read_parquet('{parquet_path}')
            """).fetchone()
            t1 = time.perf_counter()
            times.append(t1 - t0)

        avg_time = statistics.mean(times)
        r["avg_agg_s"] = round(avg_time, 4)
        print(f"  {table_name:20s} COUNT+COUNT(DISTINCT {first_col})  {_fmt_duration(avg_time):>10s}")


def _bench_filter(conn: duckdb.DuckDBPyConnection, results: list[dict]) -> None:
    print("\n  [4/6] Filter Scan")
    print("  -----------------")

    for r in results:
        table_name = r["table"]
        parquet_path = PARQUET_PATHS[table_name]
        schema = conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        ).fetchall()
        first_col = schema[0][0]

        times = []
        filtered = 0
        for i in range(3):
            t0 = time.perf_counter()
            rel = conn.execute(f"""
                SELECT COUNT(*) FROM read_parquet('{parquet_path}')
                WHERE "{first_col}" IS NOT NULL
            """)
            row = rel.fetchone()
            t1 = time.perf_counter()
            if i == 0:
                filtered = row[0]
            times.append(t1 - t0)

        avg_time = statistics.mean(times)
        r["avg_filter_s"] = round(avg_time, 4)
        r["filtered_rows"] = filtered
        print(f"  {table_name:20s} WHERE {first_col} NOT NULL  "
              f"{_fmt_duration(avg_time):>10s}  ({filtered:,} rows)")


def _bench_schema_inference(conn: duckdb.DuckDBPyConnection, results: list[dict]) -> None:
    print("\n  [5/6] Schema Inference")
    print("  ----------------------")

    for r in results:
        table_name = r["table"]
        parquet_path = PARQUET_PATHS[table_name]

        times = []
        col_count = 0
        for i in range(3):
            t0 = time.perf_counter()
            rel = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')")
            cols = rel.fetchall()
            t1 = time.perf_counter()
            if i == 0:
                col_count = len(cols)
            times.append(t1 - t0)

        avg_time = statistics.mean(times)
        r["avg_schema_s"] = round(avg_time, 4)
        r["column_count"] = col_count
        print(f"  {table_name:20s} {col_count:2d} columns  {_fmt_duration(avg_time):>10s}")


def _bench_incremental_simulation(conn: duckdb.DuckDBPyConnection, results: list[dict]) -> None:
    print("\n  [6/6] Incremental Load Simulation (Watermark)")
    print("  ----------------------------------------------")

    for r in results:
        table_name = r["table"]
        parquet_path = PARQUET_PATHS[table_name]
        schema = conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        ).fetchall()
        first_col = schema[0][0]

        times = []
        new_rows = 0
        for i in range(3):
            t0 = time.perf_counter()
            rel = conn.execute(f"""
                SELECT COUNT(*) FROM read_parquet('{parquet_path}')
                WHERE "{first_col}" >= ''
            """)
            row = rel.fetchone()
            t1 = time.perf_counter()
            if i == 0:
                new_rows = row[0]
            times.append(t1 - t0)

        avg_time = statistics.mean(times)
        r["avg_incremental_s"] = round(avg_time, 4)
        r["incremental_rows"] = new_rows
        print(f"  {table_name:20s} {_fmt_duration(avg_time):>10s}  ({new_rows:,} rows)")


def run_live_benchmark() -> dict:
    print("=" * 70)
    print("  ELYESSA-IMDB - LIVE DATABASE BENCHMARK (DuckDB Engine)")
    print("=" * 70)
    print(f"  Date:        {datetime.now().isoformat()}")
    print(f"  DuckDB:      {duckdb.__version__}")
    print(f"  Engine:      DuckDB in-memory (4 threads, 2GB mem)")
    print(f"  Source dir:  {BRONZE_PARQUET_DIR}")
    print(f"  Total size:  {_fmt_bytes(sum(os.path.getsize(PARQUET_PATHS[t]) for t in SOURCE_TABLES))}")
    print("=" * 70)

    conn = _init_duckdb()

    results = _bench_parquet_read(conn)
    _bench_column_projection(conn, results)
    _bench_aggregation(conn, results)
    _bench_filter(conn, results)
    _bench_schema_inference(conn, results)
    _bench_incremental_simulation(conn, results)

    conn.close()

    total_rows = sum(r["rows"] for r in results)
    total_size = sum(r["file_size"] for r in results)
    total_read_time = sum(r["avg_read_s"] for r in results)
    total_rows_expected = sum(REAL_ROW_COUNTS.get(t, 0) for t in SOURCE_TABLES)

    row_matches = [r for r in results if r["row_match_pct"] is not None]
    avg_row_match = statistics.mean([r["row_match_pct"] for r in row_matches]) if row_matches else 0

    print("\n" + "=" * 70)
    print("  BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"  {'Total rows read':30s} {total_rows:>12,}")
    print(f"  {'Expected rows (blueprint)':30s} {total_rows_expected:>12,}")
    print(f"  {'Row count accuracy':30s} {avg_row_match:.2f}%")
    print(f"  {'Total Parquet size':30s} {_fmt_bytes(total_size):>12s}")
    print(f"  {'Total scan time (avg)':30s} {_fmt_duration(total_read_time):>12s}")
    print(f"  {'Overall throughput':30s} {_fmt_throughput(total_rows, total_read_time):>12s}")
    print(f"  {'Pipeline throughput estimate':30s} "
          f"{_fmt_throughput(total_rows_expected, total_read_time):>12s}")
    print("=" * 70)

    report = {
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "engine": f"DuckDB {duckdb.__version__}",
            "python_version": "3.14.3",
            "mode": "in-memory (4 threads)",
            "bronze_path": BRONZE_PARQUET_DIR,
        },
        "summary": {
            "total_rows": total_rows,
            "total_rows_expected": total_rows_expected,
            "row_accuracy_pct": round(avg_row_match, 2),
            "total_parquet_size": total_size,
            "total_parquet_size_str": _fmt_bytes(total_size),
            "total_scan_time_s": round(total_read_time, 4),
            "overall_throughput_rows_per_s": round(total_rows / total_read_time) if total_read_time > 0 else 0,
            "estimated_pipeline_time_s": round(total_read_time * 1.5, 2),
        },
        "results": results,
    }

    return report


if __name__ == "__main__":
    report = run_live_benchmark()
    out_dir = os.path.join(os.path.dirname(__file__), "benchmarks")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "live_benchmark_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to {out_path}")
