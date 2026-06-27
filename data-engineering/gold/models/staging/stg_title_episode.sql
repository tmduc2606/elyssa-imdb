SELECT
    e.tconst,
    e.parent_tconst,
    e.season_number,
    e.episode_number,
    b.primary_title AS series_title,
    b.start_year AS series_start_year
FROM {{ source('silver', 'title_episode') }} e
LEFT JOIN {{ source('silver', 'title_basics') }} b
    ON e.parent_tconst = b.tconst
    AND b.is_current = TRUE
