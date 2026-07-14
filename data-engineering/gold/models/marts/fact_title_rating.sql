SELECT
    tconst AS title_key,
    snapshot_date,
    average_rating,
    num_votes,
    batch_id,
    ingested_at
FROM {{ source('silver', 'title_rating') }}
