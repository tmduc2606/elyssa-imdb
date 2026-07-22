{{ config(
    materialized='table',
    schema='gold'
) }}

SELECT
    a.nconst AS actor_a_nconst,
    a.primary_name AS actor_a_name,
    b.nconst AS actor_b_nconst,
    b.primary_name AS actor_b_name,
    a.tconst AS shared_title,
    a.title_type,
    a.start_year,
    a.average_rating,
    ROW_NUMBER() OVER (
        PARTITION BY a.nconst, b.nconst
        ORDER BY a.num_votes DESC
    ) AS collaboration_rank,
    COUNT(*) OVER (PARTITION BY a.nconst, b.nconst) AS total_collaborations
FROM {{ ref('fact_performance') }} a
JOIN {{ ref('fact_performance') }} b
    ON a.tconst = b.tconst
    AND a.nconst < b.nconst
    AND a.category IN ('actor', 'actress')
    AND b.category IN ('actor', 'actress')
LEFT JOIN {{ ref('dim_title') }} t
    ON a.tconst = t.tconst
