FK_CHECKS = [
    {
        "name": "title_episode_parent_exists",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.title_episode e
            LEFT JOIN silver.title_basics b ON e.parent_tconst = b.tconst AND b.is_current = TRUE
            WHERE b.tconst IS NULL
        """,
        "threshold": 0,
    },
    {
        "name": "title_rating_title_exists",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.title_rating r
            LEFT JOIN silver.title_basics b ON r.tconst = b.tconst AND b.is_current = TRUE
            WHERE b.tconst IS NULL
        """,
        "threshold": 0,
    },
    {
        "name": "title_director_title_exists",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.title_director d
            LEFT JOIN silver.title_basics b ON d.tconst = b.tconst AND b.is_current = TRUE
            WHERE b.tconst IS NULL
        """,
        "threshold": 0,
    },
    {
        "name": "title_writer_title_exists",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.title_writer w
            LEFT JOIN silver.title_basics b ON w.tconst = b.tconst AND b.is_current = TRUE
            WHERE b.tconst IS NULL
        """,
        "threshold": 0,
    },
    {
        "name": "title_principal_title_exists",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.title_principal p
            LEFT JOIN silver.title_basics b ON p.tconst = b.tconst AND b.is_current = TRUE
            WHERE b.tconst IS NULL
        """,
        "threshold": 0,
    },
    {
        "name": "title_genre_title_exists",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.title_genre g
            LEFT JOIN silver.title_basics b ON g.tconst = b.tconst AND b.is_current = TRUE
            WHERE b.tconst IS NULL
        """,
        "threshold": 0,
    },
    {
        "name": "name_known_for_title_exists",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.name_known_for_title k
            LEFT JOIN silver.title_basics b ON k.tconst = b.tconst AND b.is_current = TRUE
            WHERE b.tconst IS NULL
        """,
        "threshold": 0,
    },
    {
        "name": "fact_performance_nconst_exists_in_name_basics",
        "sql": """
            SELECT COUNT(*) AS orphan_count
            FROM silver.title_principal p
            LEFT JOIN silver.name_basics n ON p.nconst = n.nconst AND n.is_current = TRUE
            WHERE n.nconst IS NULL
        """,
        "threshold": 0,
    },
]

def run_fk_checks(conn) -> list[dict]:
    results = []
    all_passed = True
    for check in FK_CHECKS:
        cur = conn.cursor()
        cur.execute(check["sql"])
        count = cur.fetchone()[0]
        passed = count <= check["threshold"]
        results.append({
            "check_name": check["name"],
            "orphan_count": count,
            "threshold": check["threshold"],
            "passed": passed,
        })
        if not passed:
            all_passed = False
    return results, all_passed
