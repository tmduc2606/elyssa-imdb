WITH person_base AS (
    SELECT * FROM {{ ref('stg_name_basics') }}
),
professions AS (
    SELECT
        nconst,
        STRING_AGG(profession, ', ' ORDER BY profession_order) AS profession_list
    FROM {{ source('silver', 'name_profession') }}
    GROUP BY nconst
),
known_for AS (
    SELECT
        k.nconst,
        STRING_AGG(tb.primary_title, ', ' ORDER BY k.known_for_order) AS known_for_titles
    FROM {{ source('silver', 'name_known_for_title') }} k
    LEFT JOIN {{ ref('stg_title_basics') }} tb ON k.tconst = tb.tconst
    GROUP BY k.nconst
)
SELECT
    pb.nconst,
    pb.primary_name,
    pb.birth_year,
    pb.death_year,
    CASE
        WHEN pb.birth_year IS NOT NULL AND pb.death_year IS NOT NULL
            THEN pb.death_year - pb.birth_year
        ELSE NULL
    END AS age_at_death,
    pr.profession_list,
    kf.known_for_titles,
    pb.batch_id,
    pb.ingested_at
FROM person_base pb
LEFT JOIN professions pr ON pb.nconst = pr.nconst
LEFT JOIN known_for kf ON pb.nconst = kf.nconst
