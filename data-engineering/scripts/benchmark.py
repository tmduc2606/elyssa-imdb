"""
Elyssa-IMDb Pipeline — End-to-End Benchmark
Measures performance of each pipeline layer with configurable data sizes.
Generates a comprehensive benchmark report.
"""
import os
import sys
import time
import json
import tempfile
import statistics
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import lit, current_timestamp

# ─── Benchmark Configuration ──────────────────────────────────────────────────

BENCHMARK_CONFIGS = {
    "small": {"n_titles": 100, "n_names": 50, "iterations": 3},
    "medium": {"n_titles": 1000, "n_names": 500, "iterations": 2},
    "large": {"n_titles": 10000, "n_names": 5000, "iterations": 1},
}

TITLE_BASICS_SCHEMA = StructType([
    StructField("tconst", StringType(), False),
    StructField("titleType", StringType(), True),
    StructField("primaryTitle", StringType(), True),
    StructField("originalTitle", StringType(), True),
    StructField("isAdult", StringType(), True),
    StructField("startYear", StringType(), True),
    StructField("endYear", StringType(), True),
    StructField("runtimeMinutes", StringType(), True),
    StructField("genres", StringType(), True),
])

NAME_BASICS_SCHEMA = StructType([
    StructField("nconst", StringType(), False),
    StructField("primaryName", StringType(), True),
    StructField("birthYear", StringType(), True),
    StructField("deathYear", StringType(), True),
    StructField("primaryProfession", StringType(), True),
    StructField("knownForTitles", StringType(), True),
])


def generate_titles(n: int) -> List[tuple]:
    genres = ["Drama", "Comedy", "Action", "Thriller", "Horror", "Romance", "Sci-Fi"]
    data = []
    for i in range(n):
        g = "|".join(genres[i % len(genres):(i % len(genres)) + 2])
        data.append((
            f"tt{i:07d}", "movie", f"Title {i}", f"Original {i}",
            "0", str(1900 + (i % 130)), "\\N", str(90 + (i % 180)), g
        ))
    return data


def generate_names(n: int) -> List[tuple]:
    profs = ["actor", "director", "producer", "writer"]
    data = []
    for i in range(n):
        p = "|".join(profs[i % len(profs):(i % len(profs)) + 2])
        data.append((
            f"nm{i:07d}", f"Person {i}", str(1900 + (i % 120)),
            "\\N", p, ",".join([f"tt{j:07d}" for j in range(i, min(i + 3, n))])
        ))
    return data


# ─── Benchmark Runner ─────────────────────────────────────────────────────────

class BenchmarkRunner:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.results = []

    def benchmark_bronze_ingestion(self, n_titles: int, n_names: int) -> Dict[str, Any]:
        """Benchmark Bronze layer ingestion"""
        times = []

        for _ in range(3):
            start = time.perf_counter()

            # Create and write titles
            titles = generate_titles(n_titles)
            df = self.spark.createDataFrame(titles, TITLE_BASICS_SCHEMA)
            df = df.withColumn("_batch_id", lit("benchmark"))
            bronze_dir = os.path.join(tempfile.gettempdir(), "elyssa_benchmark_bronze")
            os.makedirs(bronze_dir, exist_ok=True)
            df.write.mode("overwrite").parquet(os.path.join(bronze_dir, "title.basics"))

            # Create and write names
            names = generate_names(n_names)
            df = self.spark.createDataFrame(names, NAME_BASICS_SCHEMA)
            df = df.withColumn("_batch_id", lit("benchmark"))
            df.write.mode("overwrite").parquet(os.path.join(bronze_dir, "name.basics"))

            elapsed = time.perf_counter() - start
            times.append(elapsed)

        return {
            "layer": "bronze",
            "operation": "ingestion",
            "n_titles": n_titles,
            "n_names": n_names,
            "total_records": n_titles + n_names,
            "times": times,
            "avg_seconds": round(statistics.mean(times), 3),
            "min_seconds": round(min(times), 3),
            "max_seconds": round(max(times), 3),
            "stddev_seconds": round(statistics.stdev(times), 3) if len(times) > 1 else 0,
            "throughput_records_per_sec": round((n_titles + n_names) / statistics.mean(times), 0),
        }

    def benchmark_silver_transform(self, n_titles: int) -> Dict[str, Any]:
        """Benchmark Silver layer transforms"""
        from silver.transform import rename_to_silver, cast_types, empty_to_null, explode_array

        times = []

        for _ in range(3):
            start = time.perf_counter()

            # Read Bronze
            df = self.spark.read.parquet(os.path.join(tempfile.gettempdir(), "elyssa_benchmark_bronze", "title.basics"))

            # Apply transforms
            df = rename_to_silver(df, "title.basics")
            df = cast_types(df, "title.basics")
            df = empty_to_null(df)

            # Explode arrays
            exploded = explode_array(df, "title.basics")
            silver_dir = os.path.join(tempfile.gettempdir(), "elyssa_benchmark_silver")
            os.makedirs(silver_dir, exist_ok=True)
            for _, exploded_df in exploded:
                exploded_df.write.mode("overwrite").parquet(os.path.join(silver_dir, "title_genre"))

            # Write main table
            df.write.mode("overwrite").parquet(os.path.join(silver_dir, "title_basics"))

            elapsed = time.perf_counter() - start
            times.append(elapsed)

        return {
            "layer": "silver",
            "operation": "transform",
            "n_titles": n_titles,
            "times": times,
            "avg_seconds": round(statistics.mean(times), 3),
            "min_seconds": round(min(times), 3),
            "max_seconds": round(max(times), 3),
            "stddev_seconds": round(statistics.stdev(times), 3) if len(times) > 1 else 0,
            "throughput_records_per_sec": round(n_titles / statistics.mean(times), 0),
        }

    def benchmark_explode_array(self, n_titles: int) -> Dict[str, Any]:
        """Benchmark array explosion"""
        from silver.transform import explode_array

        times = []

        for _ in range(3):
            start = time.perf_counter()

            df = self.spark.read.parquet(os.path.join(tempfile.gettempdir(), "elyssa_benchmark_bronze", "title.basics"))
            df = rename_to_silver(df, "title.basics")
            df = cast_types(df, "title.basics")
            df = empty_to_null(df)

            exploded = explode_array(df, "title.basics")
            for _, exploded_df in exploded:
                exploded_df.count()  # Force evaluation

            elapsed = time.perf_counter() - start
            times.append(elapsed)

        return {
            "layer": "silver",
            "operation": "explode_array",
            "n_titles": n_titles,
            "times": times,
            "avg_seconds": round(statistics.mean(times), 3),
            "throughput_records_per_sec": round(n_titles / statistics.mean(times), 0),
        }

    def benchmark_schema_validation(self, n_titles: int) -> Dict[str, Any]:
        """Benchmark schema validation"""
        from bronze.config import SOURCE_SCHEMAS, get_column_list

        times = []

        for _ in range(100):
            start = time.perf_counter()
            for table in SOURCE_SCHEMAS:
                get_column_list(table)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        return {
            "layer": "bronze",
            "operation": "schema_validation",
            "n_lookups": 100 * len(SOURCE_SCHEMAS),
            "times": times,
            "avg_ms": round(statistics.mean(times) * 1000, 2),
            "min_ms": round(min(times) * 1000, 2),
            "max_ms": round(max(times) * 1000, 2),
        }

    def run_full_benchmark(self, config_name: str = "medium") -> Dict[str, Any]:
        """Run full benchmark suite"""
        config = BENCHMARK_CONFIGS[config_name]
        n_titles = config["n_titles"]
        n_names = config["n_names"]

        print(f"\n{'=' * 70}")
        print(f"BENCHMARK: {config_name.upper()} ({n_titles} titles, {n_names} names)")
        print(f"{'=' * 70}")

        results = {
            "config": config_name,
            "timestamp": datetime.now().isoformat(),
            "benchmarks": [],
        }

        # Bronze ingestion
        print("\n[1/4] Bronze Ingestion...", end="", flush=True)
        bronze_result = self.benchmark_bronze_ingestion(n_titles, n_names)
        results["benchmarks"].append(bronze_result)
        print(f" {bronze_result['avg_seconds']:.2f}s ({bronze_result['throughput_records_per_sec']:.0f} rec/s)")

        # Silver transform
        print("[2/4] Silver Transform...", end="", flush=True)
        silver_result = self.benchmark_silver_transform(n_titles)
        results["benchmarks"].append(silver_result)
        print(f" {silver_result['avg_seconds']:.2f}s ({silver_result['throughput_records_per_sec']:.0f} rec/s)")

        # Array explosion
        print("[3/4] Array Explosion...", end="", flush=True)
        explode_result = self.benchmark_explode_array(n_titles)
        results["benchmarks"].append(explode_result)
        print(f" {explode_result['avg_seconds']:.2f}s ({explode_result['throughput_records_per_sec']:.0f} rec/s)")

        # Schema validation
        print("[4/4] Schema Validation...", end="", flush=True)
        schema_result = self.benchmark_schema_validation(n_titles)
        results["benchmarks"].append(schema_result)
        print(f" {schema_result['avg_ms']:.2f}ms avg")

        # Calculate totals
        total_time = sum(b.get("avg_seconds", 0) for b in results["benchmarks"])
        results["total_avg_seconds"] = round(total_time, 3)

        print(f"\n{'=' * 70}")
        print(f"BENCHMARK COMPLETE")
        print(f"{'=' * 70}")
        print(f"  Total avg time: {total_time:.2f}s")
        print(f"  Throughput: {n_titles / total_time:.0f} titles/s")

        return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Elyssa-IMDb Pipeline Benchmark")
    parser.add_argument("--config", choices=["small", "medium", "large"], default="medium")
    parser.add_argument("--output", default="./benchmark_results.json")
    args = parser.parse_args()

    spark = SparkSession.builder \
        .appName("ElyssaBenchmark") \
        .master("local[1]") \
        .config("spark.sql.warehouse.dir", os.path.join(tempfile.gettempdir(), "elyssa_benchmark_warehouse")) \
        .config("spark.driver.memory", "2g") \
        .config("spark.hadoop.fs.file.impl.disable.cache", "true") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    try:
        runner = BenchmarkRunner(spark)
        results = runner.run_full_benchmark(args.config)

        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n  Results saved to: {args.output}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
