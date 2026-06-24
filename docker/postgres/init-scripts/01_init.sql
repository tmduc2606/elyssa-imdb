-- Elyssa-IMDb | PostgreSQL Init Scripts
-- Runs on first container startup to create schema skeleton

-- Create extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create schemas for Medallion Architecture
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Grant permissions
GRANT ALL ON SCHEMA bronze TO elyssa;
GRANT ALL ON SCHEMA silver TO elyssa;
GRANT ALL ON SCHEMA gold TO elyssa;

-- Create graph sync tracking table (used by Airflow Neo4j sync)
CREATE TABLE IF NOT EXISTS public.graph_sync_status (
    sync_id        SERIAL PRIMARY KEY,
    sync_name      VARCHAR(100) NOT NULL UNIQUE,
    last_sync_ts   TIMESTAMPTZ,
    rows_synced    INTEGER DEFAULT 0,
    status         VARCHAR(20) DEFAULT 'pending',
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Create data quality log table
CREATE TABLE IF NOT EXISTS public.data_quality_log (
    log_id         SERIAL PRIMARY KEY,
    check_name     VARCHAR(200) NOT NULL,
    table_name     VARCHAR(200),
    metric_name    VARCHAR(100),
    metric_value   NUMERIC,
    threshold      NUMERIC,
    passed         BOOLEAN,
    logged_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Comment for documentation
COMMENT ON TABLE public.graph_sync_status IS 'Tracks Neo4j sync completion timestamps';
COMMENT ON TABLE public.data_quality_log IS 'Stores daily data quality check results';
