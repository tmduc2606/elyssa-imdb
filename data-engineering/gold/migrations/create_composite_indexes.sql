-- Composite FK indexes for Gold fact tables
-- These accelerate multi-key joins between fact tables and dimensions.
-- Created as a migration; run after dbt run completes.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_performance_tconst_ordering
    ON gold.fact_performance(tconst, ordering);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_performance_nconst
    ON gold.fact_performance(nconst);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_title_principal_title_order
    ON gold.fact_title_principal(title_key, ordering);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_title_principal_name_key
    ON gold.fact_title_principal(name_key);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_episode_series_season_episode
    ON gold.fact_episode(series_key, season_number, episode_number);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_title_rating_title_snapshot
    ON gold.fact_title_rating(title_key, snapshot_date);

-- Partial index for actor/actress queries in agg_actor_cooccurrence
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_performance_actor_category
    ON gold.fact_performance(tconst, nconst)
    WHERE category IN ('actor', 'actress');
