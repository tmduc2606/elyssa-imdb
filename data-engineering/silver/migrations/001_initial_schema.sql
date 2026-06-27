-- Schema Versioning Migration Tracker
-- Additive-only schema changes; versioned breaking changes
-- Per Blueprint: DE.13 (additive-only), DE.15 (versioned breaking changes)

CREATE TABLE IF NOT EXISTS silver.schema_versions (
    version_id      SERIAL PRIMARY KEY,
    schema_name     VARCHAR(100) NOT NULL,
    table_name      VARCHAR(200) NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    change_type     VARCHAR(20) NOT NULL CHECK (change_type IN ('additive', 'breaking', 'rollback')),
    ddl_statement   TEXT NOT NULL,
    applied_by      VARCHAR(100) DEFAULT CURRENT_USER,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    rollback_ddl    TEXT,
    UNIQUE (schema_name, table_name, version)
);

CREATE INDEX IF NOT EXISTS idx_schema_versions_lookup
    ON silver.schema_versions(schema_name, table_name, is_current);

COMMENT ON TABLE silver.schema_versions IS 'Tracks all DDL changes for audit and rollback';
COMMENT ON COLUMN silver.schema_versions.change_type IS 'additive (new cols), breaking (type changes, drops), rollback';

-- ─── Migration: v1 — Initial Silver schema (baseline) ────────────────
INSERT INTO silver.schema_versions (schema_name, table_name, version, change_type, ddl_statement)
VALUES
('silver', 'title_basics', 1, 'additive', 'CREATE TABLE silver.title_basics (...)'),
('silver', 'name_basics', 1, 'additive', 'CREATE TABLE silver.name_basics (...)'),
('silver', 'title_rating', 1, 'additive', 'CREATE TABLE silver.title_rating (...)'),
('silver', 'title_episode', 1, 'additive', 'CREATE TABLE silver.title_episode (...)'),
('silver', 'title_akas', 1, 'additive', 'CREATE TABLE silver.title_akas (...)'),
('silver', 'title_genre', 1, 'additive', 'CREATE TABLE silver.title_genre (...)'),
('silver', 'title_director', 1, 'additive', 'CREATE TABLE silver.title_director (...)'),
('silver', 'title_writer', 1, 'additive', 'CREATE TABLE silver.title_writer (...)'),
('silver', 'title_principal', 1, 'additive', 'CREATE TABLE silver.title_principal (...)'),
('silver', 'title_principal_char', 1, 'additive', 'CREATE TABLE silver.title_principal_char (...)'),
('silver', 'name_profession', 1, 'additive', 'CREATE TABLE silver.name_profession (...)'),
('silver', 'name_known_for_title', 1, 'additive', 'CREATE TABLE silver.name_known_for_title (...)'),
('silver', 'data_quality_log', 1, 'additive', 'CREATE TABLE silver.data_quality_log (...)'),
('silver', 'quarantine', 1, 'additive', 'CREATE TABLE silver.quarantine (...)'),
('silver', 'graph_sync_status', 1, 'additive', 'CREATE TABLE silver.graph_sync_status (...)');
