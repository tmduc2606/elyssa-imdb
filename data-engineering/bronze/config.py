SOURCE_CONFIG = {
    "title.akas": {
        "columns": ["titleId", "ordering", "title", "region", "language", "types", "attributes", "isOriginalTitle"],
        "delimiter": "\t",
        "null_value": r"\N",
        "description": "Alternative titles for titles"
    },
    "title.basics": {
        "columns": ["tconst", "titleType", "primaryTitle", "originalTitle", "isAdult", "startYear", "endYear", "runtimeMinutes", "genres"],
        "delimiter": "\t",
        "null_value": r"\N",
        "description": "Basic title information"
    },
    "title.crew": {
        "columns": ["tconst", "directors", "writers"],
        "delimiter": "\t",
        "null_value": r"\N",
        "description": "Director and writer information"
    },
    "title.episode": {
        "columns": ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
        "delimiter": "\t",
        "null_value": r"\N",
        "description": "Episode-level information"
    },
    "title.principals": {
        "columns": ["tconst", "ordering", "nconst", "category", "job", "characters"],
        "delimiter": "\t",
        "null_value": r"\N",
        "description": "Principal cast and crew"
    },
    "title.ratings": {
        "columns": ["tconst", "averageRating", "numVotes"],
        "delimiter": "\t",
        "null_value": r"\N",
        "description": "Title ratings and vote counts"
    },
    "name.basics": {
        "columns": ["nconst", "primaryName", "birthYear", "deathYear", "primaryProfession", "knownForTitles"],
        "delimiter": "\t",
        "null_value": r"\N",
        "description": "Person/name information"
    }
}

DEFAULT_OUTPUT_ROOT = "bronze/parquet"
DEFAULT_METADATA_ROOT = "bronze/logs"
