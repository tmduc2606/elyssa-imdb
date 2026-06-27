SELECT
    p.tconst,
    p.ordering,
    p.nconst,
    p.category,
    p.job,
    pc.character_name,
    p.batch_id,
    p.ingested_at
FROM {{ source('silver', 'title_principal') }} p
LEFT JOIN {{ source('silver', 'title_principal_char') }} pc
    ON p.tconst = pc.tconst
    AND p.ordering = pc.ordering
