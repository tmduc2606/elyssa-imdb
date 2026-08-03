WITH title_base AS (
    SELECT * FROM {{ ref('stg_title_basics') }}
),
genres AS (
    SELECT
        tconst,
        -- P2-9: genre order is non-contractual (gold-to-ds.md requires only
        -- comma-separated, trimmed) — dropping ORDER BY removes a 19.4M-row sort
        STRING_AGG(TRIM(genre), ', ') AS genre_list
    FROM {{ source('silver', 'title_genre') }}
    GROUP BY tconst
),
regions AS (
    SELECT
        title_id,
        -- P2-9: region/language order is non-contractual — dropping ORDER BY
        STRING_AGG(region, ', ') AS region_list,
        STRING_AGG(language, ', ') AS language_list,
        COUNT(*) AS aka_count
    FROM (
        SELECT DISTINCT title_id, region, language
        FROM {{ source('silver', 'title_akas') }}
        WHERE region IS NOT NULL
    ) distinct_akas
    GROUP BY title_id
),
directors AS (
    SELECT
        d.tconst,
        STRING_AGG(n.primary_name, ', ' ORDER BY d.ordering) AS director_names
    FROM {{ source('silver', 'title_director') }} d
    LEFT JOIN {{ ref('stg_name_basics') }} n ON d.nconst = n.nconst
    GROUP BY d.tconst
),
writers AS (
    SELECT
        w.tconst,
        STRING_AGG(n.primary_name, ', ' ORDER BY w.ordering) AS writer_names
    FROM {{ source('silver', 'title_writer') }} w
    LEFT JOIN {{ ref('stg_name_basics') }} n ON w.nconst = n.nconst
    GROUP BY w.tconst
),
ratings AS (
    SELECT
        tconst,
        average_rating,
        num_votes
    FROM {{ ref('stg_title_ratings') }}
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM {{ ref('stg_title_ratings') }})
),
episodes AS (
    SELECT * FROM {{ ref('stg_title_episode') }}
)
SELECT
    tb.tconst,
    tb.title_type,
    tb.primary_title,
    tb.original_title,
    tb.is_adult,
    tb.start_year,
    tb.end_year,
    tb.runtime_minutes,
    g.genre_list,
    d.director_names,
    w.writer_names,
    r.average_rating,
    r.num_votes,
    ep.parent_tconst,
    ep.series_title,
    ep.season_number,
    ep.episode_number,
    rg.region_list,
    rg.language_list,
    rg.aka_count,
    tb.batch_id,
    tb.ingested_at
FROM title_base tb
LEFT JOIN genres g ON tb.tconst = g.tconst
LEFT JOIN directors d ON tb.tconst = d.tconst
LEFT JOIN writers w ON tb.tconst = w.tconst
LEFT JOIN ratings r ON tb.tconst = r.tconst
LEFT JOIN episodes ep ON tb.tconst = ep.tconst
LEFT JOIN regions rg ON tb.tconst = rg.title_id
