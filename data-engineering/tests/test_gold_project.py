"""Gold layer (dbt project) structure and content tests."""

import os
import yaml

GOLD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gold")
MODELS_DIR = os.path.join(GOLD_DIR, "models")


def _read_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_sql(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestDbtProject:
    def test_dbt_project_exists(self):
        assert os.path.exists(os.path.join(GOLD_DIR, "dbt_project.yml"))

    def test_dbt_project_valid_yaml(self):
        config = _read_yaml(os.path.join(GOLD_DIR, "dbt_project.yml"))
        assert config["name"] == "imdb_gold"
        assert "models" in config
        assert "staging" in config["models"]["imdb_gold"]
        assert "intermediate" in config["models"]["imdb_gold"]
        assert "marts" in config["models"]["imdb_gold"]

    def test_dbt_project_materializations(self):
        config = _read_yaml(os.path.join(GOLD_DIR, "dbt_project.yml"))
        models = config["models"]["imdb_gold"]
        assert models["staging"]["+materialized"] == "view"
        assert models["intermediate"]["+materialized"] == "ephemeral"
        assert models["marts"]["+materialized"] == "table"


class TestSources:
    SOURCES_PATH = os.path.join(MODELS_DIR, "sources.yml")

    def test_sources_exists(self):
        assert os.path.exists(self.SOURCES_PATH)

    def test_sources_valid_yaml(self):
        config = _read_yaml(self.SOURCES_PATH)
        assert config["version"] == 2
        assert len(config["sources"]) == 1
        assert config["sources"][0]["name"] == "silver"

    def test_sources_has_all_tables(self):
        config = _read_yaml(self.SOURCES_PATH)
        tables = [t["name"] for t in config["sources"][0]["tables"]]
        expected = [
            "title_basics", "name_basics", "title_episode", "title_rating",
            "title_genre", "title_director", "title_writer",
            "title_principal", "title_principal_char",
            "name_profession", "name_known_for_title",
            "title_akas", "data_quality_log",
        ]
        for table in expected:
            assert table in tables, f"Table {table} not in sources"


class TestStagingModels:
    def test_staging_dir_exists(self):
        assert os.path.isdir(os.path.join(MODELS_DIR, "staging"))

    def test_staging_models_exist(self):
        expected = [
            "stg_title_basics.sql", "stg_name_basics.sql",
            "stg_title_episode.sql", "stg_title_ratings.sql",
            "stg_title_akas.sql",
        ]
        for model in expected:
            assert os.path.exists(os.path.join(MODELS_DIR, "staging", model)), \
                f"Staging model {model} not found"

    def test_staging_models_select_from_source(self):
        for model_file in os.listdir(os.path.join(MODELS_DIR, "staging")):
            if model_file.endswith(".sql"):
                content = _read_sql(os.path.join(MODELS_DIR, "staging", model_file))
                assert "{{ source(" in content, f"{model_file} doesn't select from source"

    def test_staging_models_filter_current(self):
        for model_file in ["stg_title_basics.sql", "stg_name_basics.sql"]:
            content = _read_sql(os.path.join(MODELS_DIR, "staging", model_file))
            assert "is_current = TRUE" in content, \
                f"{model_file} doesn't filter is_current"


class TestIntermediateModels:
    def test_intermediate_dir_exists(self):
        assert os.path.isdir(os.path.join(MODELS_DIR, "intermediate"))

    def test_intermediate_models_exist(self):
        expected = ["int_title_details.sql", "int_person_details.sql"]
        for model in expected:
            assert os.path.exists(os.path.join(MODELS_DIR, "intermediate", model)), \
                f"Intermediate model {model} not found"

    def test_intermediate_models_use_ref(self):
        for model_file in os.listdir(os.path.join(MODELS_DIR, "intermediate")):
            if model_file.endswith(".sql"):
                content = _read_sql(os.path.join(MODELS_DIR, "intermediate", model_file))
                assert "{{ ref(" in content or "{{ source(" in content, \
                    f"{model_file} doesn't use ref or source"

    def test_title_details_has_joins(self):
        content = _read_sql(os.path.join(MODELS_DIR, "intermediate", "int_title_details.sql"))
        assert "LEFT JOIN" in content
        assert "genre" in content.lower()
        assert "director" in content.lower()
        assert "rating" in content.lower()

    def test_person_details_has_demographics(self):
        content = _read_sql(os.path.join(MODELS_DIR, "intermediate", "int_person_details.sql"))
        assert "birth_year" in content
        assert "death_year" in content
        assert "profession" in content.lower()


class TestMartModels:
    def test_marts_dir_exists(self):
        assert os.path.isdir(os.path.join(MODELS_DIR, "marts"))

    def test_mart_models_exist(self):
        expected = [
            "dim_title.sql", "dim_person.sql", "fact_performance.sql",
            "fact_title_rating.sql", "fact_title_principal.sql",
            "agg_actor_cooccurrence.sql",
        ]
        for model in expected:
            assert os.path.exists(os.path.join(MODELS_DIR, "marts", model)), \
                f"Mart model {model} not found"

    def test_episodic_content_mart_exists(self):
        assert os.path.exists(os.path.join(
            MODELS_DIR, "marts", "episodic_content", "fact_episode.sql"))

    def test_dim_title_star_schema(self):
        content = _read_sql(os.path.join(MODELS_DIR, "marts", "dim_title.sql"))
        assert "SELECT" in content
        assert "tconst" in content
        assert "primary_title" in content
        assert "title_type" in content
        assert "genre" in content.lower()
        assert "director" in content.lower()
        assert "rating" in content.lower()
        assert "popularity_segment" in content
        assert "rating_bucket" in content

    def test_dim_person_star_schema(self):
        content = _read_sql(os.path.join(MODELS_DIR, "marts", "dim_person.sql"))
        assert "SELECT" in content
        assert "nconst" in content
        assert "primary_name" in content
        assert "birth_year" in content
        assert "generation" in content
        assert "profession" in content.lower()

    def test_fact_performance_star_schema(self):
        content = _read_sql(os.path.join(MODELS_DIR, "marts", "fact_performance.sql"))
        assert "SELECT" in content
        assert "tconst" in content
        assert "nconst" in content
        assert "category" in content
        assert "character_name" in content

    def test_mart_models_select_from_intermediate_or_source(self):
        for model_file in ["dim_title.sql", "dim_person.sql"]:
            content = _read_sql(os.path.join(MODELS_DIR, "marts", model_file))
            assert "{{ ref(" in content, f"{model_file} doesn't use ref"


class TestSchemaTests:
    def test_schema_tests_exists(self):
        assert os.path.exists(os.path.join(GOLD_DIR, "tests", "schema.yml"))

    def test_schema_tests_valid_yaml(self):
        config = _read_yaml(os.path.join(GOLD_DIR, "tests", "schema.yml"))
        assert config["version"] == 2
        assert len(config["models"]) == 6

    def test_schema_tests_cover_all_marts(self):
        config = _read_yaml(os.path.join(GOLD_DIR, "tests", "schema.yml"))
        model_names = [m["name"] for m in config["models"]]
        expected = [
            "dim_title", "dim_person", "fact_title_rating",
            "fact_title_principal", "fact_performance", "agg_actor_cooccurrence",
        ]
        for name in expected:
            assert name in model_names, f"Model {name} missing from schema tests"

    def test_dim_title_has_pk_test(self):
        config = _read_yaml(os.path.join(GOLD_DIR, "tests", "schema.yml"))
        dim_title = next(m for m in config["models"] if m["name"] == "dim_title")
        tconst_col = next(c for c in dim_title["columns"] if c["name"] == "tconst")
        assert "unique" in tconst_col["tests"]
        assert "not_null" in tconst_col["tests"]

    def test_dim_person_has_pk_test(self):
        config = _read_yaml(os.path.join(GOLD_DIR, "tests", "schema.yml"))
        dim_person = next(m for m in config["models"] if m["name"] == "dim_person")
        nconst_col = next(c for c in dim_person["columns"] if c["name"] == "nconst")
        assert "unique" in nconst_col["tests"]
        assert "not_null" in nconst_col["tests"]
