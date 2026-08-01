WITH current_count AS (
    SELECT COUNT(*) AS cnt
    FROM {{ source('silver', 'title_basics') }}
    WHERE is_current = TRUE
),
previous_count AS (
    SELECT COALESCE(metric_value, 0) AS prev_cnt
    FROM {{ source('silver', 'data_quality_log') }}
    WHERE check_name = 'row_count_title_basics'
      AND metric_name = 'row_count_variance'
      AND passed = TRUE
    ORDER BY logged_at DESC
    LIMIT 1
)
SELECT
    c.cnt AS current_row_count,
    p.prev_cnt AS previous_row_count,
    ABS(c.cnt - p.prev_cnt) / NULLIF(p.prev_cnt, 0) AS deviation_ratio
FROM current_count c
CROSS JOIN previous_count p
WHERE p.prev_cnt > 0
  AND ABS(c.cnt - p.prev_cnt) / p.prev_cnt > 0.2
