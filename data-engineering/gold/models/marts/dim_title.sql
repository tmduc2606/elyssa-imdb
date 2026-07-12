SELECT
    tconst,
    title_type,
    primary_title,
    original_title,
    is_adult,
    start_year,
    end_year,
    runtime_minutes,
    genre_list,
    director_names,
    writer_names,
    average_rating,
    num_votes,
    CASE
        WHEN num_votes IS NOT NULL AND num_votes >= 100000 THEN 'high'
        WHEN num_votes IS NOT NULL AND num_votes >= 10000 THEN 'medium'
        WHEN num_votes IS NOT NULL THEN 'low'
        ELSE 'unknown'
    END AS popularity_segment,
    CASE
        WHEN average_rating IS NOT NULL AND average_rating >= 8.0 THEN 'excellent'
        WHEN average_rating IS NOT NULL AND average_rating >= 6.0 THEN 'good'
        WHEN average_rating IS NOT NULL THEN 'average'
        ELSE 'unrated'
    END AS rating_bucket,
    parent_tconst,
    series_title,
    season_number,
    episode_number,
    region_list,
    language_list,
    aka_count
FROM {{ ref('int_title_details') }}
