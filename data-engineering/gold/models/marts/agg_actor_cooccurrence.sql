{{ config(
    materialized='table',
    schema='gold'
) }}

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
FROM {{ ref('fact_performance') }} a
JOIN {{ ref('fact_performance') }} b
    ON a.tconst = b.tconst
    AND a.nconst < b.nconst
    AND a.category IN ('actor', 'actress')
    AND b.category IN ('actor', 'actress')
LEFT JOIN {{ ref('dim_title') }} t
    ON a.tconst = t.tconst
LEFT JOIN {{ ref('dim_person') }} pa
    ON a.nconst = pa.nconst
LEFT JOIN {{ ref('dim_person') }} pb
    ON b.nconst = pb.nconst
