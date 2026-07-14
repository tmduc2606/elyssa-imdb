"""
Gold Layer Comprehensive Tests & Benchmarks
Validates: dbt project structure, model SQL, schema tests, star schema design
"""
import os
import sys
import time
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

GOLD_DIR = os.path.join(os.path.dirname(__file__), '..')
MODELS_DIR = os.path.join(GOLD_DIR, 'models')

# ─── dbt Project Tests ────────────────────────────────────────────────────────

class TestDbtProject:
    """Tests for gold/dbt_project.yml"""

    def test_dbt_project_exists(self):
        assert os.path.exists(os.path.join(GOLD_DIR, 'dbt_project.yml'))

    def test_dbt_project_valid_yaml(self):
        path = os.path.join(GOLD_DIR, 'dbt_project.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        assert config['name'] == 'imdb_gold'
        assert 'models' in config
        assert 'staging' in config['models']['imdb_gold']
        assert 'intermediate' in config['models']['imdb_gold']
        assert 'marts' in config['models']['imdb_gold']

    def test_dbt_project_materializations(self):
        path = os.path.join(GOLD_DIR, 'dbt_project.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        models = config['models']['imdb_gold']
        assert models['staging']['+materialized'] == 'view'
        assert models['intermediate']['+materialized'] == 'ephemeral'
        assert models['marts']['+materialized'] == 'table'

# ─── Source Definition Tests ──────────────────────────────────────────────────

class TestSources:
    """Tests for gold/sources.yml"""

    def test_sources_exists(self):
        assert os.path.exists(os.path.join(GOLD_DIR, 'sources.yml'))

    def test_sources_valid_yaml(self):
        path = os.path.join(GOLD_DIR, 'sources.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        assert config['version'] == 2
        assert len(config['sources']) == 1
        assert config['sources'][0]['name'] == 'silver'

    def test_sources_has_all_tables(self):
        path = os.path.join(GOLD_DIR, 'sources.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        tables = [t['name'] for t in config['sources'][0]['tables']]
        expected = [
            'title_basics', 'name_basics', 'title_episode', 'title_rating',
            'title_genre', 'title_director', 'title_writer',
            'title_principal', 'title_principal_char',
            'name_profession', 'name_known_for_title',
        ]
        for table in expected:
            assert table in tables, f"Table {table} not in sources"

# ─── Staging Model Tests ─────────────────────────────────────────────────────

class TestStagingModels:
    """Tests for gold/models/staging/"""

    def test_staging_dir_exists(self):
        assert os.path.isdir(os.path.join(MODELS_DIR, 'staging'))

    def test_staging_models_exist(self):
        expected = [
            'stg_title_basics.sql',
            'stg_name_basics.sql',
            'stg_title_episode.sql',
            'stg_title_ratings.sql',
        ]
        for model in expected:
            path = os.path.join(MODELS_DIR, 'staging', model)
            assert os.path.exists(path), f"Staging model {model} not found"

    def test_staging_models_select_from_source(self):
        for model_file in os.listdir(os.path.join(MODELS_DIR, 'staging')):
            if model_file.endswith('.sql'):
                path = os.path.join(MODELS_DIR, 'staging', model_file)
                with open(path) as f:
                    content = f.read()
                assert "{{ source(" in content, f"{model_file} doesn't select from source"

    def test_staging_models_filter_current(self):
        for model_file in ['stg_title_basics.sql', 'stg_name_basics.sql']:
            path = os.path.join(MODELS_DIR, 'staging', model_file)
            with open(path) as f:
                content = f.read()
            assert "is_current = TRUE" in content, f"{model_file} doesn't filter is_current"

# ─── Intermediate Model Tests ────────────────────────────────────────────────

class TestIntermediateModels:
    """Tests for gold/models/intermediate/"""

    def test_intermediate_dir_exists(self):
        assert os.path.isdir(os.path.join(MODELS_DIR, 'intermediate'))

    def test_intermediate_models_exist(self):
        expected = ['int_title_details.sql', 'int_person_details.sql']
        for model in expected:
            path = os.path.join(MODELS_DIR, 'intermediate', model)
            assert os.path.exists(path), f"Intermediate model {model} not found"

    def test_intermediate_models_use_ref(self):
        for model_file in os.listdir(os.path.join(MODELS_DIR, 'intermediate')):
            if model_file.endswith('.sql'):
                path = os.path.join(MODELS_DIR, 'intermediate', model_file)
                with open(path) as f:
                    content = f.read()
                assert "{{ ref(" in content or "{{ source(" in content, \
                    f"{model_file} doesn't use ref or source"

    def test_title_details_has_joins(self):
        path = os.path.join(MODELS_DIR, 'intermediate', 'int_title_details.sql')
        with open(path) as f:
            content = f.read()
        assert "LEFT JOIN" in content
        assert "genre" in content.lower()
        assert "director" in content.lower()
        assert "rating" in content.lower()

    def test_person_details_has_demographics(self):
        path = os.path.join(MODELS_DIR, 'intermediate', 'int_person_details.sql')
        with open(path) as f:
            content = f.read()
        assert "birth_year" in content
        assert "death_year" in content
        assert "profession" in content.lower()

# ─── Mart Model Tests ────────────────────────────────────────────────────────

class TestMartModels:
    """Tests for gold/models/marts/ — Star Schema Design"""

    def test_marts_dir_exists(self):
        assert os.path.isdir(os.path.join(MODELS_DIR, 'marts'))

    def test_mart_models_exist(self):
        expected = ['dim_title.sql', 'dim_person.sql', 'fact_performance.sql']
        for model in expected:
            path = os.path.join(MODELS_DIR, 'marts', model)
            assert os.path.exists(path), f"Mart model {model} not found"

    def test_dim_title_star_schema(self):
        path = os.path.join(MODELS_DIR, 'marts', 'dim_title.sql')
        with open(path) as f:
            content = f.read()
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
        path = os.path.join(MODELS_DIR, 'marts', 'dim_person.sql')
        with open(path) as f:
            content = f.read()
        assert "SELECT" in content
        assert "nconst" in content
        assert "primary_name" in content
        assert "birth_year" in content
        assert "generation" in content
        assert "profession" in content.lower()

    def test_fact_performance_star_schema(self):
        path = os.path.join(MODELS_DIR, 'marts', 'fact_performance.sql')
        with open(path) as f:
            content = f.read()
        assert "SELECT" in content
        assert "tconst" in content
        assert "nconst" in content
        assert "category" in content
        assert "character_name" in content

    def test_mart_models_select_from_intermediate_or_source(self):
        for model_file in ['dim_title.sql', 'dim_person.sql']:
            path = os.path.join(MODELS_DIR, 'marts', model_file)
            with open(path) as f:
                content = f.read()
            assert "{{ ref(" in content, f"{model_file} doesn't use ref"

# ─── Schema Tests ─────────────────────────────────────────────────────────────

class TestSchemaTests:
    """Tests for gold/tests/schema.yml"""

    def test_schema_tests_exists(self):
        assert os.path.exists(os.path.join(GOLD_DIR, 'tests', 'schema.yml'))

    def test_schema_tests_valid_yaml(self):
        path = os.path.join(GOLD_DIR, 'tests', 'schema.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        assert config['version'] == 2
        assert len(config['models']) == 3

    def test_schema_tests_cover_all_marts(self):
        path = os.path.join(GOLD_DIR, 'tests', 'schema.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        model_names = [m['name'] for m in config['models']]
        assert 'dim_title' in model_names
        assert 'dim_person' in model_names
        assert 'fact_performance' in model_names

    def test_dim_title_has_pk_test(self):
        path = os.path.join(GOLD_DIR, 'tests', 'schema.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        dim_title = next(m for m in config['models'] if m['name'] == 'dim_title')
        tconst_col = next(c for c in dim_title['columns'] if c['name'] == 'tconst')
        assert 'unique' in tconst_col['tests']
        assert 'not_null' in tconst_col['tests']

    def test_dim_person_has_pk_test(self):
        path = os.path.join(GOLD_DIR, 'tests', 'schema.yml')
        with open(path) as f:
            config = yaml.safe_load(f)
        dim_person = next(m for m in config['models'] if m['name'] == 'dim_person')
        nconst_col = next(c for c in dim_person['columns'] if c['name'] == 'nconst')
        assert 'unique' in nconst_col['tests']
        assert 'not_null' in nconst_col['tests']

# ─── Performance Benchmarks ───────────────────────────────────────────────────

class TestGoldPerformance:
    """Performance benchmarks for Gold layer"""

    def test_sql_parse_time(self):
        start = time.perf_counter()
        for _ in range(100):
            for model_dir in ['staging', 'intermediate', 'marts']:
                dir_path = os.path.join(MODELS_DIR, model_dir)
                if os.path.isdir(dir_path):
                    for f in os.listdir(dir_path):
                        if f.endswith('.sql'):
                            with open(os.path.join(dir_path, f)) as fh:
                                fh.read()
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 100, f"SQL parse avg {avg_ms:.1f}ms > 100ms threshold"

    def test_yaml_parse_time(self):
        start = time.perf_counter()
        for _ in range(100):
            for f in ['dbt_project.yml', 'sources.yml', 'tests/schema.yml']:
                path = os.path.join(GOLD_DIR, f)
                if os.path.exists(path):
                    with open(path) as fh:
                        yaml.safe_load(fh)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 50, f"YAML parse avg {avg_ms:.1f}ms > 50ms threshold"
