SELECT
    nconst,
    primary_name,
    birth_year,
    death_year,
    batch_id,
    ingested_at
FROM {{ source('silver', 'name_basics') }}
WHERE is_current = TRUE
