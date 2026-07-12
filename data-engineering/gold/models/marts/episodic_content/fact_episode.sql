SELECT
    e.tconst AS episode_key,
    e.parent_tconst AS series_key,
    e.season_number,
    e.episode_number,
    tb.primary_title AS series_title,
    tb.start_year AS series_start_year,
    tb.title_type AS series_type,
    e.batch_id,
    e.ingested_at
FROM {{ source('silver', 'title_episode') }} e
LEFT JOIN {{ source('silver', 'title_basics') }} tb
    ON e.parent_tconst = tb.tconst
    AND tb.is_current = TRUE
    AND tb.title_type IN ('tvSeries', 'tvMiniSeries')
