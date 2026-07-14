"""
Silver ETL Runner — Orchestrates Bronze → Silver pipeline.

Usage:
    spark-submit etl_runner.py \\
        --bronze-path /data/bronze/ \\
        --jdbc-url jdbc:postgresql://postgres:5432/imdb \\
        --jdbc-user user --jdbc-password pass
"""

import argparse
from pyspark.sql import SparkSession
from silver.transform import empty_to_null, cast_types, rename_to_silver, explode_array
from silver.upsert import SILVER_TABLE_DDL
from silver.fk_checks import run_fk_checks


BRONZE_SOURCE_MAP = {
    "title.basics": "title.basics",
    "title.akas": "title.akas",
    "title.crew": "title.crew",
    "title.episode": "title.episode",
    "title.principals": "title.principals",
    "title.ratings": "title.ratings",
    "name.basics": "name.basics",
}


def read_bronze(spark: SparkSession, bronze_path: str, source: str):
    path = f"{bronze_path}/{source}"
    df = spark.read.parquet(path)
    df = rename_to_silver(df, source)
    df = cast_types(df, source)
    df = empty_to_null(df)
    return df


def upsert_to_silver(df, target_table: str, jdbc_url: str, jdbc_user: str, jdbc_password: str):
    table_config = SILVER_TABLE_DDL.get(target_table)
    if table_config is None:
        raise ValueError(f"Unknown target table: {target_table}")
    pk_cols = table_config["pk"]
    join_conditions = " AND ".join([f"target.{c} = source.{c}" for c in pk_cols])

    df.createOrReplaceTempView("source_view")
    spark = df.sparkSession

    if "merge_cols" in table_config:
        update_conditions = " OR ".join([
            f"target.{c} IS DISTINCT FROM source.{c}"
            for c in table_config["merge_cols"]
        ])
        update_set = ", ".join([
            f"{c} = source.{c}" for c in table_config["merge_cols"]
        ])
        merge_sql = f"""
        MERGE INTO {target_table} AS target
        USING source_view AS source
        ON {join_conditions}
        WHEN MATCHED AND ({update_conditions}) THEN
            UPDATE SET valid_to = NOW(), is_current = FALSE
        WHEN NOT MATCHED THEN
            INSERT
            VALUES ({', '.join([f'source.`{c}`' for c in df.columns])}, NOW(), NULL, TRUE, NULL, NOW())
        """
    else:
        merge_sql = f"""
        MERGE INTO {target_table} AS target
        USING source_view AS source
        ON {join_conditions}
        WHEN NOT MATCHED THEN
            INSERT ({', '.join(df.columns)})
            VALUES ({', '.join([f'source.`{c}`' for c in df.columns])})
        WHEN MATCHED THEN
            UPDATE SET {', '.join([f'{c} = source.`{c}`' for c in df.columns if c not in pk_cols])}
        """

    spark.sql(merge_sql)


def main():
    parser = argparse.ArgumentParser(description="Silver ETL Runner")
    parser.add_argument("--bronze-path", required=True)
    parser.add_argument("--jdbc-url", required=True)
    parser.add_argument("--jdbc-user", required=True)
    parser.add_argument("--jdbc-password", required=True)
    args = parser.parse_args()

    spark = SparkSession.builder \
        .appName("Silver ETL") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    for source, target in BRONZE_SOURCE_MAP.items():
        print(f"[ETL] Processing {source} -> {target}")
        df = read_bronze(spark, args.bronze_path, source)

        # Write main table
        upsert_to_silver(df, f"silver.{target}", args.jdbc_url, args.jdbc_user, args.jdbc_password)

        # Explode arrays into sub-tables
        exploded_tables = explode_array(df, source)
        for sub_table, exploded_df in exploded_tables:
            print(f"[ETL] Exploding -> {sub_table}")
            upsert_to_silver(exploded_df, sub_table, args.jdbc_url, args.jdbc_user, args.jdbc_password)

    # FK integrity checks
    results, all_passed = run_fk_checks(spark)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[FK] {status}: {r['check_name']} ({r['orphan_count']} orphans)")
    if not all_passed:
        raise RuntimeError("FK integrity checks failed — quarantining affected batches")

    print("[ETL] Silver layer update complete")
    spark.stop()


if __name__ == "__main__":
    main()
