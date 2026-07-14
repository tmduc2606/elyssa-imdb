-- Elyssa-IMDb | Silver Schema Application
-- Runs after 01_init.sql (alphabetical order)
-- Creates tables in elyssa_warehouse.silver schema
-- (runs against POSTGRES_DB=elyssa_warehouse, no \c needed)

CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS gold;

GRANT ALL ON SCHEMA silver TO elyssa;
GRANT ALL ON SCHEMA bronze TO elyssa;
GRANT ALL ON SCHEMA gold TO elyssa;

-- Extensions (needed in imdb_silver for timescaledb)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Sequences for Surrogate Keys
CREATE SEQUENCE IF NOT EXISTS silver.title_key_seq START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS silver.name_key_seq START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS silver.character_key_seq START 1 INCREMENT 1;

-- 1. Title Basics
CREATE TABLE IF NOT EXISTS silver.title_basics (
    title_key       INTEGER PRIMARY KEY DEFAULT nextval('silver.title_key_seq'),
    tconst          VARCHAR(20) NOT NULL,
    title_type      VARCHAR(50) NOT NULL,
    primary_title   TEXT NOT NULL,
    original_title  TEXT NOT NULL,
    is_adult        BOOLEAN NOT NULL DEFAULT FALSE,
    start_year      SMALLINT,
    end_year        SMALLINT,
    runtime_minutes INTEGER,
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to        TIMESTAMPTZ,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    batch_id        VARCHAR(20),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_title_basics_tconst UNIQUE (tconst)
);
CREATE INDEX IF NOT EXISTS idx_title_basics_tconst ON silver.title_basics(tconst);
CREATE INDEX IF NOT EXISTS idx_title_basics_current ON silver.title_basics(is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_title_basics_tconst_is_current ON silver.title_basics(tconst, is_current);

-- 2. Title Genres
CREATE TABLE IF NOT EXISTS silver.title_genre (
    tconst   VARCHAR(20) NOT NULL,
    genre    VARCHAR(50) NOT NULL,
    PRIMARY KEY (tconst, genre)
);
CREATE INDEX IF NOT EXISTS idx_title_genre_tconst ON silver.title_genre(tconst);

-- 3. Title Ratings (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS silver.title_rating (
    tconst         VARCHAR(20) NOT NULL,
    average_rating NUMERIC(3,1) NOT NULL CHECK (average_rating BETWEEN 0.0 AND 10.0),
    num_votes      INTEGER NOT NULL CHECK (num_votes >= 0),
    snapshot_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    batch_id       VARCHAR(20),
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tconst, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_title_rating_snapshot ON silver.title_rating(snapshot_date DESC);
SELECT create_hypertable('silver.title_rating', 'snapshot_date', if_not_exists => TRUE);

-- 4. Title Episode
CREATE TABLE IF NOT EXISTS silver.title_episode (
    tconst         VARCHAR(20) PRIMARY KEY,
    parent_tconst  VARCHAR(20) NOT NULL,
    season_number  INTEGER,
    episode_number INTEGER,
    batch_id       VARCHAR(20),
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_title_episode_parent ON silver.title_episode(parent_tconst);

-- 5. Title AKAs
CREATE TABLE IF NOT EXISTS silver.title_akas (
    title_id         VARCHAR(20) NOT NULL,
    ordering         INTEGER NOT NULL,
    title            TEXT NOT NULL,
    region           VARCHAR(10),
    language         VARCHAR(50),
    is_original_title BOOLEAN NOT NULL DEFAULT FALSE,
    batch_id         VARCHAR(20),
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (title_id, ordering)
);
CREATE INDEX IF NOT EXISTS idx_title_akas_title_id ON silver.title_akas(title_id);

-- 6. AKA Types
CREATE TABLE IF NOT EXISTS silver.title_akas_type (
    title_id VARCHAR(20) NOT NULL,
    ordering INTEGER NOT NULL,
    type     VARCHAR(50) NOT NULL,
    PRIMARY KEY (title_id, ordering, type),
    FOREIGN KEY (title_id, ordering) REFERENCES silver.title_akas(title_id, ordering) ON DELETE CASCADE
);

-- 7. AKA Attributes
CREATE TABLE IF NOT EXISTS silver.title_akas_attribute (
    title_id VARCHAR(20) NOT NULL,
    ordering INTEGER NOT NULL,
    attr     VARCHAR(100) NOT NULL,
    PRIMARY KEY (title_id, ordering, attr),
    FOREIGN KEY (title_id, ordering) REFERENCES silver.title_akas(title_id, ordering) ON DELETE CASCADE
);

-- 8. Title Directors
CREATE TABLE IF NOT EXISTS silver.title_director (
    tconst   VARCHAR(20) NOT NULL,
    ordering SMALLINT NOT NULL,
    nconst   VARCHAR(20) NOT NULL,
    batch_id VARCHAR(20),
    PRIMARY KEY (tconst, ordering)
);
CREATE INDEX IF NOT EXISTS idx_title_director_nconst ON silver.title_director(nconst);

-- 9. Title Writers
CREATE TABLE IF NOT EXISTS silver.title_writer (
    tconst   VARCHAR(20) NOT NULL,
    ordering SMALLINT NOT NULL,
    nconst   VARCHAR(20) NOT NULL,
    batch_id VARCHAR(20),
    PRIMARY KEY (tconst, ordering)
);
CREATE INDEX IF NOT EXISTS idx_title_writer_nconst ON silver.title_writer(nconst);

-- 10. Title Principals
CREATE TABLE IF NOT EXISTS silver.title_principal (
    tconst     VARCHAR(20) NOT NULL,
    ordering   SMALLINT NOT NULL,
    nconst     VARCHAR(20) NOT NULL,
    category   VARCHAR(50) NOT NULL,
    job        TEXT,
    batch_id   VARCHAR(20),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tconst, ordering)
);
CREATE INDEX IF NOT EXISTS idx_title_principal_tconst ON silver.title_principal(tconst);
CREATE INDEX IF NOT EXISTS idx_title_principal_nconst ON silver.title_principal(nconst);

-- 11. Principal Characters
CREATE TABLE IF NOT EXISTS silver.title_principal_char (
    tconst         VARCHAR(20) NOT NULL,
    ordering       SMALLINT NOT NULL,
    character_name TEXT NOT NULL,
    PRIMARY KEY (tconst, ordering, character_name),
    FOREIGN KEY (tconst, ordering) REFERENCES silver.title_principal(tconst, ordering) ON DELETE CASCADE
);

-- 12. Name Basics
CREATE TABLE IF NOT EXISTS silver.name_basics (
    name_key     INTEGER PRIMARY KEY DEFAULT nextval('silver.name_key_seq'),
    nconst       VARCHAR(20) NOT NULL,
    primary_name TEXT NOT NULL,
    birth_year   SMALLINT,
    death_year   SMALLINT,
    valid_from   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to     TIMESTAMPTZ,
    is_current   BOOLEAN NOT NULL DEFAULT TRUE,
    batch_id     VARCHAR(20),
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_name_basics_nconst UNIQUE (nconst)
);
CREATE INDEX IF NOT EXISTS idx_name_basics_nconst ON silver.name_basics(nconst);
CREATE INDEX IF NOT EXISTS idx_name_basics_current ON silver.name_basics(is_current) WHERE is_current = TRUE;

-- 13. Name Professions
CREATE TABLE IF NOT EXISTS silver.name_profession (
    nconst           VARCHAR(20) NOT NULL,
    profession_order SMALLINT NOT NULL CHECK (profession_order BETWEEN 1 AND 3),
    profession       VARCHAR(100) NOT NULL,
    PRIMARY KEY (nconst, profession_order)
);
CREATE INDEX IF NOT EXISTS idx_name_profession_nconst ON silver.name_profession(nconst);

-- 14. Known-For Titles
CREATE TABLE IF NOT EXISTS silver.name_known_for_title (
    nconst          VARCHAR(20) NOT NULL,
    known_for_order SMALLINT NOT NULL CHECK (known_for_order BETWEEN 1 AND 4),
    tconst          VARCHAR(20) NOT NULL,
    PRIMARY KEY (nconst, known_for_order)
);
CREATE INDEX IF NOT EXISTS idx_name_known_for_nconst ON silver.name_known_for_title(nconst);
CREATE INDEX IF NOT EXISTS idx_name_known_for_tconst ON silver.name_known_for_title(tconst);

-- Governance / Quality Tables
CREATE TABLE IF NOT EXISTS silver.graph_sync_status (
    sync_id       SERIAL PRIMARY KEY,
    sync_name     VARCHAR(100) NOT NULL UNIQUE,
    last_sync_ts  TIMESTAMPTZ,
    rows_synced   INTEGER DEFAULT 0,
    status        VARCHAR(20) DEFAULT 'pending',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.data_quality_log (
    log_id       SERIAL PRIMARY KEY,
    check_name   VARCHAR(200) NOT NULL,
    table_name   VARCHAR(200),
    metric_name  VARCHAR(100),
    metric_value NUMERIC,
    threshold    NUMERIC,
    passed       BOOLEAN,
    batch_id     VARCHAR(20),
    logged_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.quarantine (
    quarantine_id  SERIAL PRIMARY KEY,
    table_name     VARCHAR(200) NOT NULL,
    batch_id       VARCHAR(20),
    check_name     VARCHAR(200) NOT NULL,
    failed_value   TEXT,
    error_message  TEXT,
    raw_record     JSONB,
    quarantined_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.batch_metadata (
    metadata_id    SERIAL PRIMARY KEY,
    batch_id       VARCHAR(20) NOT NULL,
    table_name     VARCHAR(200) NOT NULL,
    source_file    TEXT,
    file_checksum  VARCHAR(64),
    row_count      INTEGER,
    ingested_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_title_akas_type_ref ON silver.title_akas_type(title_id, ordering);
CREATE INDEX IF NOT EXISTS idx_title_akas_attribute_ref ON silver.title_akas_attribute(title_id, ordering);
CREATE INDEX IF NOT EXISTS idx_title_principal_char_ref ON silver.title_principal_char(tconst, ordering);
CREATE INDEX IF NOT EXISTS idx_quarantine_batch ON silver.quarantine(batch_id);
CREATE INDEX IF NOT EXISTS idx_dq_log_batch ON silver.data_quality_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_metadata_batch ON silver.batch_metadata(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_metadata_table ON silver.batch_metadata(table_name);

COMMENT ON TABLE silver.batch_metadata IS 'Batch-level checksum and lineage tracking per source table';

CREATE INDEX IF NOT EXISTS idx_title_genre_tconst_genre ON silver.title_genre(tconst, genre);
CREATE INDEX IF NOT EXISTS idx_title_director_tconst ON silver.title_director(tconst);
CREATE INDEX IF NOT EXISTS idx_title_writer_tconst ON silver.title_writer(tconst);
