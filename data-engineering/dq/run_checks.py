"""
Data Quality Check Runner

Reads DQ config, executes checks against Silver PostgreSQL,
and logs results to silver.data_quality_log and silver.quarantine.
"""

import argparse
import yaml
import json


DEFAULT_CHECKS = [
    {
        "name": "null_rate_title_basics",
        "table": "silver.title_basics",
        "metric": "null_rate",
        "column": "primary_title",
        "threshold": 0.0,
        "severity": "error",
    },
    {
        "name": "null_rate_title_rating",
        "table": "silver.title_rating",
        "metric": "null_rate",
        "column": "average_rating",
        "threshold": 0.0,
        "severity": "error",
    },
    {
        "name": "referential_title_episode",
        "table": "silver.title_episode",
        "metric": "orphan_rate",
        "fk_column": "parent_tconst",
        "pk_table": "silver.title_basics",
        "pk_column": "tconst",
        "threshold": 0.01,
        "severity": "warn",
    },
    {
        "name": "row_count_title_basics",
        "table": "silver.title_basics",
        "metric": "row_count_variance",
        "expected_min": 100000,
        "threshold": 0.2,
        "severity": "error",
    },
    {
        "name": "row_count_name_basics",
        "table": "silver.name_basics",
        "metric": "row_count_variance",
        "expected_min": 100000,
        "threshold": 0.2,
        "severity": "error",
    },
]


def run_checks(config_path: str, jdbc_url: str, jdbc_user: str, jdbc_password: str):
    import psycopg2

    if config_path:
        with open(config_path) as f:
            checks = yaml.safe_load(f).get("checks", [])
    else:
        checks = DEFAULT_CHECKS

    conn = psycopg2.connect(jdbc_url, user=jdbc_user, password=jdbc_password)
    cursor = conn.cursor()
    all_passed = True

    for check in checks:
        name = check["name"]
        table = check["table"]
        metric = check["metric"]
        threshold = check["threshold"]

        try:
            if metric == "null_rate":
                col = check["column"]
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                total = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
                nulls = cursor.fetchone()[0]
                value = nulls / max(total, 1)

            elif metric == "orphan_rate":
                fk_col = check["fk_column"]
                pk_table = check["pk_table"]
                pk_col = check["pk_column"]
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                total = cursor.fetchone()[0]
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table} f
                    LEFT JOIN {pk_table} p ON f.{fk_col} = p.{pk_col} AND p.is_current = TRUE
                    WHERE p.{pk_col} IS NULL
                """)
                orphans = cursor.fetchone()[0]
                value = orphans / max(total, 1)

            elif metric == "row_count_variance":
                expected_min = check.get("expected_min", 0)
                expected_count = check.get("expected_count", 0)
                alert_threshold_pct = check.get("alert_threshold_pct", 20)
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                if expected_count > 0:
                    value = abs(count - expected_count) / expected_count
                elif expected_min > 0:
                    value = abs(count - expected_min) / expected_min
                else:
                    value = 0.0
                passed = value <= threshold
                if not passed:
                    cursor.execute(f"""
                        INSERT INTO silver.data_quality_log
                            (check_name, table_name, metric_name, metric_value, threshold, passed, batch_id, logged_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (f"{name}_alert", table, "row_count_deviation",
                          value, alert_threshold_pct / 100.0, False, None))
                    print(f"[DQ] ALERT: {name} — row count deviation {value:.2%} exceeds {alert_threshold_pct}%")

            else:
                continue

            if metric != "row_count_variance":
                passed = value <= threshold
            cursor.execute(f"""
                INSERT INTO silver.data_quality_log
                    (check_name, table_name, metric_name, metric_value, threshold, passed, batch_id, logged_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (name, table, metric, value, threshold, passed, None))

            status = "PASS" if passed else "FAIL"
            print(f"[DQ] {status}: {name} = {value:.4f} (threshold: {threshold})")
            all_passed = all_passed and passed

        except Exception as e:
            cursor.execute(f"""
                INSERT INTO silver.quarantine
                    (table_name, check_name, error_message, quarantined_at)
                VALUES (%s, %s, %s, NOW())
            """, (table, name, str(e)))
            print(f"[DQ] ERROR: {name} — {e}")

    conn.commit()
    cursor.close()
    conn.close()
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Data Quality Runner")
    parser.add_argument("--config", default="")
    parser.add_argument("--jdbc-url", required=True)
    parser.add_argument("--jdbc-user", required=True)
    parser.add_argument("--jdbc-password", required=True)
    args = parser.parse_args()

    passed = run_checks(args.config, args.jdbc_url, args.jdbc_user, args.jdbc_password)
    if not passed:
        raise RuntimeError("Data quality checks failed")
    print("[DQ] All checks passed")


if __name__ == "__main__":
    main()
