from pyspark.sql import DataFrame

SILVER_TABLE_DDL = {
    "silver.title_basics": {
        "pk": ["tconst"],
        "merge_cols": ["title_type", "primary_title", "original_title", "is_adult", "start_year", "end_year", "runtime_minutes"],
    },
    "silver.title_rating": {"pk": ["tconst", "snapshot_date"]},
    "silver.title_episode": {"pk": ["tconst"]},
    "silver.title_akas": {"pk": ["title_id", "ordering"]},
    "silver.title_genre": {"pk": ["tconst", "genre"]},
    "silver.title_akas_type": {"pk": ["title_id", "ordering", "type"]},
    "silver.title_akas_attribute": {"pk": ["title_id", "ordering", "attr"]},
    "silver.title_director": {"pk": ["tconst", "ordering"]},
    "silver.title_writer": {"pk": ["tconst", "ordering"]},
    "silver.title_principal": {"pk": ["tconst", "ordering"]},
    "silver.title_principal_char": {"pk": ["tconst", "ordering", "character_name"]},
    "silver.name_basics": {
        "pk": ["nconst"],
        "merge_cols": ["primary_name", "birth_year", "death_year"],
    },
    "silver.name_profession": {"pk": ["nconst", "profession_order"]},
    "silver.name_known_for_title": {"pk": ["nconst", "known_for_order"]},
}

def generate_merge_sql(target_table: str, df: DataFrame) -> tuple[str, str]:
    table_config = SILVER_TABLE_DDL[target_table]
    pk_cols = table_config["pk"]
    df_cols = [f'"{c}"' for c in df.columns]

    staging_table = f"{target_table}_stage"

    create_staging = f"""
    CREATE TEMP VIEW {staging_table.replace('.', '_')} AS
    SELECT {', '.join(df_cols)} FROM staging_{target_table.split('.')[-1]}
    """

    join_conditions = " AND ".join([f"target.{c} = source.{c}" for c in pk_cols])

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
        USING {staging_table.replace('.', '_')} AS source
        ON {join_conditions}
        WHEN MATCHED AND ({update_conditions}) THEN
            UPDATE SET valid_to = NOW(), is_current = FALSE
        WHEN NOT MATCHED THEN
            INSERT ({', '.join(df_cols)}, valid_from, is_current)
            VALUES ({', '.join([f'source.{c}' for c in df.columns])}, NOW(), TRUE)
        """
    else:
        merge_sql = f"""
        MERGE INTO {target_table} AS target
        USING {staging_table.replace('.', '_')} AS source
        ON {join_conditions}
        WHEN NOT MATCHED THEN
            INSERT ({', '.join(df_cols)})
            VALUES ({', '.join([f'source.{c}' for c in df.columns])})
        WHEN MATCHED THEN
            UPDATE SET {', '.join([f'{c} = source.{c}' for c in df.columns if c not in pk_cols])}
        """

    return create_staging, merge_sql
