-- P1-6: this model ENOSPC'd on DSM parallel gather once (a8779df fix).
-- With 2 cores the parallel hash join gains nothing; disabling it per-model
-- removes the shared-memory failure mode entirely.
{{ config(
    materialized='table',
    pre_hook="SET max_parallel_workers_per_gather = 0"
) }}

WITH perf AS (
    -- fact_performance is at (tconst, ordering, character) grain: the same
    -- person can hold multiple actor/actress rows in one title (different
    -- orderings, multi-character principals). Dedup to (tconst, nconst) so
    -- the self-join yields exactly one row per actor pair per title.
    SELECT DISTINCT
        tconst,
        nconst
    FROM {{ ref('fact_performance') }}
    WHERE category IN ('actor', 'actress')
)

SELECT
    a.nconst AS actor_a_nconst,
    pa.primary_name AS actor_a_name,
    b.nconst AS actor_b_nconst,
    pb.primary_name AS actor_b_name,
    a.tconst AS shared_title,
    t.title_type,
    t.start_year,
    t.average_rating,
    t.num_votes,
    ROW_NUMBER() OVER (
        PARTITION BY a.nconst, b.nconst
        ORDER BY t.num_votes DESC NULLS LAST
    ) AS collaboration_rank,
    COUNT(*) OVER (PARTITION BY a.nconst, b.nconst) AS total_collaborations
FROM perf a
JOIN perf b
    ON a.tconst = b.tconst
    AND a.nconst < b.nconst
LEFT JOIN {{ ref('dim_title') }} t
    ON a.tconst = t.tconst
LEFT JOIN {{ ref('dim_person') }} pa
    ON a.nconst = pa.nconst
LEFT JOIN {{ ref('dim_person') }} pb
    ON b.nconst = pb.nconst
