SELECT
    tconst,
    title_type,
    primary_title,
    original_title,
    is_adult,
    start_year,
    end_year,
    runtime_minutes,
    batch_id,
    ingested_at
FROM {{ source('silver', 'title_basics') }}
WHERE is_current = TRUE
