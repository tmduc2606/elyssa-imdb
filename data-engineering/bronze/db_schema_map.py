DB_TO_BRONZE_COLUMN_MAP: dict[str, dict[str, str]] = {
    "title.basics": {
        "tconst": "tconst",
        "title_type": "titleType",
        "primary_title": "primaryTitle",
        "original_title": "originalTitle",
        "is_adult": "isAdult",
        "start_year": "startYear",
        "end_year": "endYear",
        "runtime_minutes": "runtimeMinutes",
    },
    "title.akas": {
        "title_id": "titleId",
        "ordering": "ordering",
        "title": "title",
        "region": "region",
        "language": "language",
        "is_original_title": "isOriginalTitle",
    },
    "title.crew": {
        "tconst": "tconst",
        "directors": "directors",
        "writers": "writers",
    },
    "title.episode": {
        "tconst": "tconst",
        "parent_tconst": "parentTconst",
        "season_number": "seasonNumber",
        "episode_number": "episodeNumber",
    },
    "title.principals": {
        "tconst": "tconst",
        "ordering": "ordering",
        "nconst": "nconst",
        "category": "category",
        "job": "job",
    },
    "title.ratings": {
        "tconst": "tconst",
        "average_rating": "averageRating",
        "num_votes": "numVotes",
        "snapshot_date": "snapshotDate",
    },
    "name.basics": {
        "nconst": "nconst",
        "primary_name": "primaryName",
        "birth_year": "birthYear",
        "death_year": "deathYear",
    },
}


def get_bronze_columns(source_name: str) -> list[str]:
    return list(DB_TO_BRONZE_COLUMN_MAP[source_name].values())


def get_db_columns(source_name: str) -> list[str]:
    return list(DB_TO_BRONZE_COLUMN_MAP[source_name].keys())


def map_row_to_bronze(row: dict, source_name: str) -> dict:
    col_map = DB_TO_BRONZE_COLUMN_MAP[source_name]
    return {col_map[k]: v for k, v in row.items() if k in col_map}
