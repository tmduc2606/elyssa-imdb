{{ config(
    materialized='incremental',
    unique_key=['title_key', 'ordering'],
    on_schema_change='append_new_columns'
) }}

SELECT
    p.tconst AS title_key,
    p.nconst AS name_key,
    pc.character_name,
    p.ordering,
    p.category,
    p.job,
    p.batch_id,
    p.ingested_at
FROM {{ source('silver', 'title_principal') }} p
LEFT JOIN {{ source('silver', 'title_principal_char') }} pc
    ON p.tconst = pc.tconst
    AND p.ordering = pc.ordering
{% if is_incremental() %}
  WHERE p.ingested_at > (SELECT max(ingested_at) FROM {{ this }})
{% endif %}
