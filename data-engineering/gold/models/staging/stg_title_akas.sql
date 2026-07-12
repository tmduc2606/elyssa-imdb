SELECT
    title_id,
    title AS aka_title,
    region,
    language,
    is_original_title,
    batch_id,
    ingested_at
FROM {{ source('silver', 'title_akas') }}
