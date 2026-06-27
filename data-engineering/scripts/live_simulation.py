"""
Elyssa-IMDb Pipeline — Live Simulation
Simulates the full Bronze → Silver → Gold pipeline end-to-end with synthetic data.
Creates temporary directories, writes Parquet, runs transforms, validates results.
"""
import os
import sys
import time
import json
import shutil
import tempfile
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, BooleanType,
    IntegerType, ShortType, DecimalType
)
from pyspark.sql.functions import lit, current_timestamp, col, when

# ─── Test Data Generation ─────────────────────────────────────────────────────

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

TITLE_RATINGS_SCHEMA = StructType([
    StructField("tconst", StringType(), False),
    StructField("averageRating", StringType(), True),
    StructField("numVotes", StringType(), True),
])

TITLE_EPISODE_SCHEMA = StructType([
    StructField("tconst", StringType(), False),
    StructField("parentTconst", StringType(), True),
    StructField("seasonNumber", StringType(), True),
    StructField("episodeNumber", StringType(), True),
])

TITLE_AKAS_SCHEMA = StructType([
    StructField("titleId", StringType(), False),
    StructField("ordering", StringType(), True),
    StructField("title", StringType(), True),
    StructField("region", StringType(), True),
    StructField("language", StringType(), True),
    StructField("isOriginalTitle", StringType(), True),
    StructField("types", StringType(), True),
    StructField("attributes", StringType(), True),
])

TITLE_CREW_SCHEMA = StructType([
    StructField("tconst", StringType(), False),
    StructField("directors", StringType(), True),
    StructField("writers", StringType(), True),
])

TITLE_PRINCIPALS_SCHEMA = StructType([
    StructField("tconst", StringType(), False),
    StructField("ordering", StringType(), True),
    StructField("nconst", StringType(), True),
    StructField("category", StringType(), True),
    StructField("job", StringType(), True),
    StructField("characters", StringType(), True),
])


def generate_title_basics(n=1000):
    types = ["movie", "short", "tvSeries", "tvEpisode", "video", "tvMovie"]
    genres_list = ["Drama", "Comedy", "Action", "Thriller", "Horror", "Romance",
                   "Sci-Fi", "Animation", "Documentary", "Crime"]
    data = []
    for i in range(n):
        t = types[i % len(types)]
        g = "|".join(genres_list[i % len(genres_list):(i % len(genres_list)) + 2])
        year = 1890 + (i % 140)
        runtime = 10 + (i % 200)
        data.append((
            f"tt{i:07d}", t, f"Title {i}", f"Original Title {i}",
            "1" if i % 10 == 0 else "0",
            str(year), "\\N" if i % 5 == 0 else str(year + 1),
            str(runtime), g
        ))
    return data


def generate_name_basics(n=500):
    professions = ["actor", "actress", "director", "producer", "writer", "editor", "cinematographer"]
    data = []
    for i in range(n):
        prof = "|".join(professions[i % len(professions):(i % len(professions)) + 2])
        titles = ",".join([f"tt{j:07d}" for j in range(i, min(i + 4, n))])
        data.append((
            f"nm{i:07d}", f"Person {i}",
            str(1900 + (i % 120)),
            "\\N" if i % 3 == 0 else str(1950 + (i % 70)),
            prof, titles
        ))
    return data


def generate_title_ratings(n=1000):
    data = []
    for i in range(n):
        data.append((
            f"tt{i:07d}",
            str(round(3.0 + (i % 70) / 10.0, 1)),
            str(10 + (i % 100000))
        ))
    return data


def generate_title_episode(n=500):
    data = []
    for i in range(n):
        parent = f"tt{i:07d}" if i < n else f"tt{i // 10:07d}"
        data.append((
            f"tt{i:07d}", parent,
            str(1 + (i % 10)), str(1 + (i % 20))
        ))
    return data


def generate_title_akas(n=200):
    regions = ["US", "GB", "FR", "DE", "JP", "IN", "BR", "ES", "IT", "KR"]
    types = ["imdbDisplay", "original", "french", "german", "japanese"]
    data = []
    for i in range(n):
        data.append((
            f"tt{i:07d}", str(1 + (i % 5)),
            f"Title {i} ({regions[i % len(regions)]})",
            regions[i % len(regions)],
            regions[i % len(regions)].lower(),
            "1" if i % 10 == 0 else "0",
            types[i % len(types)], ""
        ))
    return data


def generate_title_crew(n=500):
    data = []
    for i in range(n):
        dirs = ",".join([f"nm{j:07d}" for j in range(i, min(i + 3, n))])
        writers = ",".join([f"nm{j:07d}" for j in range(i, min(i + 2, n))])
        data.append((f"tt{i:07d}", dirs, writers))
    return data


def generate_title_principals(n=1000):
    categories = ["actor", "actress", "director", "producer", "writer", "cinematographer"]
    data = []
    for i in range(n):
        chars = f'"Character {i % 100}"' if i % 3 == 0 else None
        data.append((
            f"tt{i:07d}", str(1 + (i % 10)),
            f"nm{i:07d}", categories[i % len(categories)],
            "director" if i % 4 == 0 else None, chars
        ))
    return data


# ─── Pipeline Simulation ─────────────────────────────────────────────────────

def run_simulation(spark, bronze_path, n_titles=1000, n_names=500):
    """Run the full pipeline simulation"""
    results = {
        "start_time": datetime.now().isoformat(),
        "stages": {},
        "metrics": {},
        "errors": [],
    }

    # ─── Stage 1: Bronze Ingestion ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 1: BRONZE INGESTION")
    print("=" * 70)

    bronze_start = time.perf_counter()

    tables = {
        "title.basics": (TITLE_BASICS_SCHEMA, generate_title_basics(n_titles)),
        "name.basics": (NAME_BASICS_SCHEMA, generate_name_basics(n_names)),
        "title.ratings": (TITLE_RATINGS_SCHEMA, generate_title_ratings(n_titles)),
        "title.episode": (TITLE_EPISODE_SCHEMA, generate_title_episode(n_titles // 2)),
        "title.akas": (TITLE_AKAS_SCHEMA, generate_title_akas(n_titles // 5)),
        "title.crew": (TITLE_CREW_SCHEMA, generate_title_crew(n_titles // 2)),
        "title.principals": (TITLE_PRINCIPALS_SCHEMA, generate_title_principals(n_titles)),
    }

    for table_name, (schema, data) in tables.items():
        print(f"  Ingesting {table_name}... ", end="", flush=True)
        df = spark.createDataFrame(data, schema)

        # Add metadata columns
        df = df.withColumn("_batch_id", lit(f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"))
        df = df.withColumn("_source_file", lit(f"{table_name}.tsv.gz"))
        df = df.withColumn("_source_table", lit(table_name))
        df = df.withColumn("_ingested_at", current_timestamp())

        # Write to Parquet
        output_path = os.path.join(bronze_path, table_name)
        df.write.mode("overwrite").parquet(output_path)
        count = df.count()
        print(f"{count} records")

    bronze_elapsed = time.perf_counter() - bronze_start
    results["stages"]["bronze"] = {
        "elapsed_seconds": round(bronze_elapsed, 2),
        "tables": list(tables.keys()),
        "total_records": sum(len(d) for _, d in tables.values()),
    }
    print(f"\n  Bronze elapsed: {bronze_elapsed:.2f}s")

    # ─── Stage 2: Silver Transform ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 2: SILVER TRANSFORM")
    print("=" * 70)

    silver_start = time.perf_counter()

    from silver.transform import rename_to_silver, cast_types, empty_to_null, explode_array

    for table_name in tables.keys():
        print(f"  Transforming {table_name}... ", end="", flush=True)
        input_path = os.path.join(bronze_path, table_name)
        df = spark.read.parquet(input_path)

        # Apply transforms
        df = rename_to_silver(df, table_name)
        df = cast_types(df, table_name)
        df = empty_to_null(df)

        # Write Silver output
        output_path = os.path.join(bronze_path, "..", "silver_sim", table_name)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.write.mode("overwrite").parquet(output_path)

        # Explode arrays
        exploded = explode_array(df, table_name)
        for sub_table, exploded_df in exploded:
            sub_output = os.path.join(bronze_path, "..", "silver_sim", sub_table.replace(".", "/"))
            os.makedirs(os.path.dirname(sub_output), exist_ok=True)
            exploded_df.write.mode("overwrite").parquet(sub_output)
            print(f"{exploded_df.count()} rows -> {sub_table}", end=" ")

        print(f"({df.count()} main rows)")

    silver_elapsed = time.perf_counter() - silver_start
    results["stages"]["silver"] = {
        "elapsed_seconds": round(silver_elapsed, 2),
        "tables_transformed": len(tables),
    }
    print(f"\n  Silver elapsed: {silver_elapsed:.2f}s")

    # ─── Stage 3: Gold Validation ──────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 3: GOLD VALIDATION")
    print("=" * 70)

    gold_start = time.perf_counter()

    # Validate Gold SQL files exist and parse
    gold_dir = os.path.join(os.path.dirname(__file__), '..', 'gold')
    sql_files = []
    for root, dirs, files in os.walk(os.path.join(gold_dir, 'models')):
        for f in files:
            if f.endswith('.sql'):
                sql_files.append(os.path.join(root, f))

    print(f"  Found {len(sql_files)} Gold SQL models")
    for sql_file in sql_files:
        with open(sql_file) as f:
            content = f.read()
        # Basic validation
        assert "SELECT" in content, f"{sql_file} missing SELECT"
        print(f"    {os.path.basename(sql_file)}: OK ({len(content)} bytes)")

    # Validate YAML files
    yaml_files = ['dbt_project.yml', 'sources.yml', 'tests/schema.yml']
    for yf in yaml_files:
        path = os.path.join(gold_dir, yf)
        if os.path.exists(path):
            import yaml
            with open(path) as f:
                yaml.safe_load(f)
            print(f"    {yf}: OK")

    gold_elapsed = time.perf_counter() - gold_start
    results["stages"]["gold"] = {
        "elapsed_seconds": round(gold_elapsed, 2),
        "sql_models": len(sql_files),
        "yaml_configs": len(yaml_files),
    }
    print(f"\n  Gold elapsed: {gold_elapsed:.2f}s")

    # ─── Stage 4: DQ Framework ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 4: DATA QUALITY FRAMEWORK")
    print("=" * 70)

    dq_start = time.perf_counter()

    import yaml as pyyaml
    dq_config_path = os.path.join(os.path.dirname(__file__), '..', 'dq', 'config.yaml')
    with open(dq_config_path) as f:
        dq_config = pyyaml.safe_load(f)

    print(f"  Loaded {len(dq_config['checks'])} DQ checks")
    for check in dq_config['checks']:
        print(f"    {check['name']}: {check['metric']} (threshold: {check['threshold']})")

    dq_elapsed = time.perf_counter() - dq_start
    results["stages"]["dq"] = {
        "elapsed_seconds": round(dq_elapsed, 2),
        "checks_loaded": len(dq_config['checks']),
    }
    print(f"\n  DQ elapsed: {dq_elapsed:.2f}s")

    # ─── Stage 5: Orchestration Validation ─────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 5: ORCHESTRATION VALIDATION")
    print("=" * 70)

    orch_start = time.perf_counter()

    dag_path = os.path.join(os.path.dirname(__file__), '..', 'orchestration', 'dags', 'imdb_pipeline_dag.py')
    with open(dag_path) as f:
        dag_content = f.read()

    # Count tasks
    task_count = dag_content.count('task_id=')
    operator_count = dag_content.count('Operator(')

    print(f"  DAG tasks: {task_count}")
    print(f"  Custom operators: {operator_count}")

    # Validate operators
    ops_dir = os.path.join(os.path.dirname(__file__), '..', 'orchestration', 'operators')
    op_files = [f for f in os.listdir(ops_dir) if f.endswith('.py') and f != '__init__.py']
    print(f"  Operator files: {len(op_files)}")

    orch_elapsed = time.perf_counter() - orch_start
    results["stages"]["orchestration"] = {
        "elapsed_seconds": round(orch_elapsed, 2),
        "dag_tasks": task_count,
        "operators": len(op_files),
    }
    print(f"\n  Orchestration elapsed: {orch_elapsed:.2f}s")

    # ─── Summary ───────────────────────────────────────────────────────────
    total_elapsed = bronze_elapsed + silver_elapsed + gold_elapsed + dq_elapsed + orch_elapsed
    results["total_elapsed_seconds"] = round(total_elapsed, 2)
    results["end_time"] = datetime.now().isoformat()

    print("\n" + "=" * 70)
    print("SIMULATION COMPLETE")
    print("=" * 70)
    print(f"  Total elapsed: {total_elapsed:.2f}s")
    print(f"  Bronze: {bronze_elapsed:.2f}s ({results['stages']['bronze']['total_records']} records)")
    print(f"  Silver: {silver_elapsed:.2f}s ({results['stages']['silver']['tables_transformed']} tables)")
    print(f"  Gold:   {gold_elapsed:.2f}s ({results['stages']['gold']['sql_models']} models)")
    print(f"  DQ:     {dq_elapsed:.2f}s ({results['stages']['dq']['checks_loaded']} checks)")
    print(f"  Orch:   {orch_elapsed:.2f}s ({results['stages']['orchestration']['dag_tasks']} tasks)")

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Elyssa-IMDb Pipeline Live Simulation")
    parser.add_argument("--n-titles", type=int, default=1000, help="Number of titles to generate")
    parser.add_argument("--n-names", type=int, default=500, help="Number of names to generate")
    parser.add_argument("--output-dir", default="./simulation_output", help="Output directory")
    args = parser.parse_args()

    print("=" * 70)
    print("ELYSSA-IMDB PIPELINE LIVE SIMULATION")
    print("=" * 70)
    print(f"  Titles: {args.n_titles}")
    print(f"  Names:  {args.n_names}")
    print(f"  Output: {args.output_dir}")

    # Create temporary directories
    bronze_path = os.path.join(args.output_dir, "bronze")
    os.makedirs(bronze_path, exist_ok=True)

    # Initialize Spark
    spark = SparkSession.builder \
        .appName("ElyssaLiveSimulation") \
        .master("local[1]") \
        .config("spark.sql.warehouse.dir", os.path.join(args.output_dir, "warehouse")) \
        .config("spark.driver.memory", "2g") \
        .config("spark.hadoop.fs.file.impl.disable.cache", "true") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        results = run_simulation(spark, bronze_path, args.n_titles, args.n_names)

        # Save results
        results_path = os.path.join(args.output_dir, "simulation_results.json")
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n  Results saved to: {results_path}")

    finally:
        spark.stop()

    return results


if __name__ == "__main__":
    main()
