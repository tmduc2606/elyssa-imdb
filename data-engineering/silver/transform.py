from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, when, split, explode, posexplode, arrays_zip, trim
from pyspark.sql.types import BooleanType, IntegerType, ShortType, DecimalType, DateType

NULL_MARKER = r"\N"

ARRAY_FIELDS = {
    "title.basics": [("genres", "\\|", "silver.title_genre", "tconst", "genre")],
    "title.akas": [
        ("types", ",", "silver.title_akas_type", "title_id,ordering", "type"),
        ("attributes", ",", "silver.title_akas_attribute", "title_id,ordering", "attr"),
    ],
    "title.crew": [
        ("directors", ",", "silver.title_director", "tconst", "nconst"),
        ("writers", ",", "silver.title_writer", "tconst", "nconst"),
    ],
    "title.principals": [("characters", ",", "silver.title_principal_char", "tconst,ordering", "character_name")],
    "name.basics": [
        ("primaryProfession", ",", "silver.name_profession", "nconst", "profession"),
        ("knownForTitles", ",", "silver.name_known_for_title", "nconst", "tconst"),
    ],
}

TYPE_MAP = {
    "title.basics": {
        "isAdult": ("is_adult", BooleanType()),
        "startYear": ("start_year", ShortType()),
        "endYear": ("end_year", ShortType()),
        "runtimeMinutes": ("runtime_minutes", IntegerType()),
    },
    "title.ratings": {
        "averageRating": ("average_rating", DecimalType(3, 1)),
        "numVotes": ("num_votes", IntegerType()),
    },
    "name.basics": {
        "birthYear": ("birth_year", ShortType()),
        "deathYear": ("death_year", ShortType()),
    },
}

def null_to_empty(df: DataFrame) -> DataFrame:
    for c in df.columns:
        df = df.withColumn(c, when(col(c).isNull(), "").otherwise(col(c)))
    return df

def empty_to_null(df: DataFrame) -> DataFrame:
    for c in df.columns:
        df = df.withColumn(
            c,
            when((col(c) == "") | (col(c) == r"\N"), None).otherwise(col(c))
        )
    return df

def cast_types(df: DataFrame, source_name: str) -> DataFrame:
    if source_name not in TYPE_MAP:
        return df
    for src_col, (target_col, dtype) in TYPE_MAP[source_name].items():
        if src_col in df.columns:
            df = df.withColumn(target_col, col(src_col).cast(dtype))
            if target_col != src_col:
                df = df.drop(src_col)
    # Filter invalid runtime values (negative or zero)
    if "runtime_minutes" in df.columns and source_name == "title.basics":
        df = df.filter((col("runtime_minutes").isNull()) | (col("runtime_minutes") > 0))
    return df

def rename_to_silver(df: DataFrame, source_name: str) -> DataFrame:
    mapping = {
        "titleId": "title_id",
        "parentTconst": "parent_tconst",
        "isOriginalTitle": "is_original_title",
        "averageRating": "average_rating",
        "numVotes": "num_votes",
        "primaryName": "primary_name",
        "birthYear": "birth_year",
        "deathYear": "death_year",
        "primaryProfession": "primary_profession",
        "knownForTitles": "known_for_titles",
        "startYear": "start_year",
        "endYear": "end_year",
        "runtimeMinutes": "runtime_minutes",
        "primaryTitle": "primary_title",
        "originalTitle": "original_title",
        "titleType": "title_type",
        "isAdult": "is_adult",
        "seasonNumber": "season_number",
        "episodeNumber": "episode_number",
        "snapshotDate": "snapshot_date",
        "characterName": "character_name",
    }
    for old, new in mapping.items():
        if old in df.columns:
            df = df.withColumnRenamed(old, new)
    return df

def explode_array(df: DataFrame, source_name: str) -> list[DataFrame]:
    if source_name not in ARRAY_FIELDS:
        return []
    result = []
    for col_name, sep, target_table, id_cols, value_col in ARRAY_FIELDS[source_name]:
        if col_name not in df.columns:
            continue
        exploded = df.select(
            *[col(c) for c in id_cols.split(",")],
            posexplode(split(col(col_name), sep)).alias("_pos", value_col)
        )
        exploded = exploded.withColumn(value_col, trim(col(value_col)))
        result.append((target_table, exploded))
    return result
