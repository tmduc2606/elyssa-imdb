{{
  config(
    materialized='incremental',
    unique_key='nconst',
    incremental_strategy='delete+insert',
    on_schema_change='append_new_columns'
  )
}}

SELECT
    nconst,
    primary_name,
    birth_year,
    death_year,
    age_at_death,
    CASE
        WHEN birth_year IS NOT NULL THEN
            CASE
                WHEN birth_year >= 2010 THEN 'Gen Alpha'
                WHEN birth_year >= 1997 THEN 'Gen Z'
                WHEN birth_year >= 1981 THEN 'Millennial'
                WHEN birth_year >= 1965 THEN 'Gen X'
                WHEN birth_year >= 1946 THEN 'Boomer'
                ELSE 'Silent/Greatest'
            END
        ELSE NULL
    END AS generation,
    profession_list,
    known_for_titles,
    known_for_ids
FROM {{ ref('int_person_details') }}
{% if is_incremental() %}
-- O1: only process people whose Silver row changed since the last build.
-- Silver SCD2 emits a new row (new ingested_at) whenever attributes change,
-- so a name-level watermark on silver.name_basics captures all updates.
WHERE nconst IN (
    SELECT DISTINCT nconst
    FROM {{ source('silver', 'name_basics') }}
    WHERE ingested_at > (SELECT COALESCE(MAX(ingested_at), TIMESTAMPTZ '1970-01-01')
                         FROM {{ this }})
)
{% endif %}
