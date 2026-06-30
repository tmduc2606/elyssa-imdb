-- FK integrity: verify all title_key references resolve
SELECT
    'title_basics' AS fk_check,
    COUNT(*) AS orphan_count
FROM {{ source('silver', 'title_episode') }} e
LEFT JOIN {{ source('silver', 'title_basics') }} b
    ON e.parent_tconst = b.tconst AND b.is_current = TRUE
WHERE b.tconst IS NULL

UNION ALL

SELECT
    'title_rating' AS fk_check,
    COUNT(*) AS orphan_count
FROM {{ source('silver', 'title_rating') }} r
LEFT JOIN {{ source('silver', 'title_basics') }} b
    ON r.tconst = b.tconst AND b.is_current = TRUE
WHERE b.tconst IS NULL

UNION ALL

SELECT
    'name_known_for' AS fk_check,
    COUNT(*) AS orphan_count
FROM {{ source('silver', 'name_known_for_title') }} k
LEFT JOIN {{ source('silver', 'title_basics') }} b
    ON k.tconst = b.tconst AND b.is_current = TRUE
WHERE b.tconst IS NULL
