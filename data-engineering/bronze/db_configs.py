from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConnection:
    host: str = "postgres"
    port: int = 5432
    database: str = "elyssa_warehouse"
    user: str = "elyssa"
    password: str = "elyssa_pg_2026"
    schema: str = "silver"
    source_type: str = "postgresql"


@dataclass
class SourceTableDef:
    source_table: str
    bronze_name: str
    columns: list[str]
    watermark_column: Optional[str] = None
    id_column: str = "tconst"
    batch_size: int = 50000
    description: str = ""


POSTGRESQL_CONFIG = DatabaseConnection()


@dataclass
class DuckDBConfig:
    source_type: str = "duckdb"
    read_only: bool = True
    threads: int = 4
    memory_limit_mb: int = 2048


DUCKDB_CONFIG = DuckDBConfig()


DUCKDB_PARQUET_SOURCES: dict[str, SourceTableDef] = {
    "title.basics": SourceTableDef(
        source_table="s3://bronze/title.basics.parquet",
        bronze_name="title.basics",
        columns=["tconst", "titleType", "primaryTitle", "originalTitle",
                 "isAdult", "startYear", "endYear", "runtimeMinutes",
                 "genres"],
        id_column="tconst",
        description="Basic title information from S3 Parquet via DuckDB",
    ),
    "title.akas": SourceTableDef(
        source_table="s3://bronze/title.akas.parquet",
        bronze_name="title.akas",
        columns=["titleId", "ordering", "title", "region", "language",
                 "types", "attributes", "isOriginalTitle"],
        id_column="titleId",
        description="Alternative titles from S3 Parquet via DuckDB",
    ),
    "title.crew": SourceTableDef(
        source_table="s3://bronze/title.crew.parquet",
        bronze_name="title.crew",
        columns=["tconst", "directors", "writers"],
        id_column="tconst",
        description="Director and writer information from S3 Parquet via DuckDB",
    ),
    "title.episode": SourceTableDef(
        source_table="s3://bronze/title.episode.parquet",
        bronze_name="title.episode",
        columns=["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
        id_column="tconst",
        description="Episode information from S3 Parquet via DuckDB",
    ),
    "title.principals": SourceTableDef(
        source_table="s3://bronze/title.principals.parquet",
        bronze_name="title.principals",
        columns=["tconst", "ordering", "nconst", "category", "job",
                 "characters"],
        id_column="tconst",
        description="Principal cast and crew from S3 Parquet via DuckDB",
    ),
    "title.ratings": SourceTableDef(
        source_table="s3://bronze/title.ratings.parquet",
        bronze_name="title.ratings",
        columns=["tconst", "averageRating", "numVotes"],
        id_column="tconst",
        description="Title ratings from S3 Parquet via DuckDB",
    ),
    "name.basics": SourceTableDef(
        source_table="s3://bronze/name.basics.parquet",
        bronze_name="name.basics",
        columns=["nconst", "primaryName", "birthYear", "deathYear",
                 "primaryProfession", "knownForTitles"],
        id_column="nconst",
        description="Person/name information from S3 Parquet via DuckDB",
    ),
}


DB_SOURCE_TABLES: dict[str, SourceTableDef] = {
    "title.basics": SourceTableDef(
        source_table="silver.title_basics",
        bronze_name="title.basics",
        columns=["tconst", "title_type", "primary_title", "original_title",
                 "is_adult", "start_year", "end_year", "runtime_minutes"],
        watermark_column="ingested_at",
        id_column="tconst",
        description="Basic title information from Silver",
    ),
    "title.akas": SourceTableDef(
        source_table="silver.title_akas",
        bronze_name="title.akas",
        columns=["title_id", "ordering", "title", "region", "language",
                 "is_original_title"],
        watermark_column="ingested_at",
        id_column="title_id",
        description="Alternative titles from Silver",
    ),
    "title.crew": SourceTableDef(
        source_table="silver.title_crew",
        bronze_name="title.crew",
        columns=["tconst", "directors", "writers"],
        watermark_column="ingested_at",
        id_column="tconst",
        description="Director and writer information from Silver",
    ),
    "title.episode": SourceTableDef(
        source_table="silver.title_episode",
        bronze_name="title.episode",
        columns=["tconst", "parent_tconst", "season_number", "episode_number"],
        watermark_column="ingested_at",
        id_column="tconst",
        description="Episode-level information from Silver",
    ),
    "title.principals": SourceTableDef(
        source_table="silver.title_principal",
        bronze_name="title.principals",
        columns=["tconst", "ordering", "nconst", "category", "job"],
        watermark_column="ingested_at",
        id_column="tconst",
        description="Principal cast and crew from Silver",
    ),
    "title.ratings": SourceTableDef(
        source_table="silver.title_rating",
        bronze_name="title.ratings",
        columns=["tconst", "average_rating", "num_votes", "snapshot_date"],
        watermark_column="ingested_at",
        id_column="tconst",
        description="Title ratings from Silver",
    ),
    "name.basics": SourceTableDef(
        source_table="silver.name_basics",
        bronze_name="name.basics",
        columns=["nconst", "primary_name", "birth_year", "death_year"],
        watermark_column="ingested_at",
        id_column="nconst",
        description="Person/name information from Silver",
    ),
}

DEFAULT_DB_OUTPUT_ROOT = "bronze/db_parquet"
DEFAULT_DB_METADATA_ROOT = "bronze/logs"
