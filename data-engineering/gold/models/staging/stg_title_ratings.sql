SELECT
    r.tconst,
    r.average_rating,
    r.num_votes,
    r.snapshot_date,
    r.batch_id,
    r.ingested_at
FROM {{ source('silver', 'title_rating') }} r
