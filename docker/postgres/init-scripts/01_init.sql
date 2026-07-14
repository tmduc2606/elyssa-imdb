-- Elyssa-IMDb | PostgreSQL Init Scripts
-- Runs on first container startup to create schema skeleton

-- Create extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create schemas for Medallion Architecture (in elyssa_warehouse)
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Grant permissions (re-applied on every rebuild)
GRANT ALL ON SCHEMA bronze TO elyssa;
GRANT ALL ON SCHEMA silver TO elyssa;
GRANT ALL ON SCHEMA gold TO elyssa;
-- Future tables in silver also get full privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA silver GRANT ALL ON TABLES TO elyssa;

-- Note: silver schema/tables are created by 02_silver_schema.sql (alphabetical order)
--       in this same elyssa_warehouse database.

-- Create graph sync tracking table (used by Airflow Neo4j sync)
-- NOTE: moved to silver schema in 02_silver_schema.sql
-- Legacy public schema tables are intentionally not created here.
-- See 02_silver_schema.sql for full silver schema definition.

-- Comment for documentation
COMMENT ON SCHEMA silver IS 'Silver layer — canonical 3NF/BCNF enterprise model with SCD2';
COMMENT ON SCHEMA gold IS 'Gold layer — denormalized star-schema marts';
