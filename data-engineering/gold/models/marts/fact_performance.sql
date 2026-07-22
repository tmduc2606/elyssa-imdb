{{ config(
    materialized='incremental',
    unique_key=['tconst', 'ordering', 'nconst', 'category'],
    on_schema_change='append_new_columns'
) }}

SELECT
    p.tconst,
    p.ordering,
    p.nconst,
    p.category,
    p.job,
    pc.character_name,
    COALESCE(p.batch_id, 'legacy') AS batch_id,
    COALESCE(p.ingested_at, '1970-01-01'::TIMESTAMPTZ) AS ingested_at
FROM {{ source('silver', 'title_principal') }} p
LEFT JOIN {{ source('silver', 'title_principal_char') }} pc
    ON p.tconst = pc.tconst
    AND p.ordering = pc.ordering
{% if is_incremental() %}
  WHERE p.ingested_at > (SELECT max(ingested_at) FROM {{ this }})
{% endif %}
