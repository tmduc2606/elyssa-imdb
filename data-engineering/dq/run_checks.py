"""
Data Quality Check Runner

Reads DQ config, executes checks against Silver PostgreSQL,
and logs results to silver.data_quality_log and silver.quarantine.
"""

import argparse
import yaml
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


def run_checks(config_path: str, jdbc_url: str, jdbc_user: str, jdbc_password: str):
    """Execute checks from config, log results to data_quality_log and quarantine."""
    import psycopg2
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timezone

    log = get_logger()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if not config_path:
        config_path = "/opt/airflow/data-engineering/dq/config.yaml"
    with open(config_path) as f:
        checks = yaml.safe_load(f).get("checks", [])

    log.log_stage(stage="dq_runner", batch_id=batch_id, status="started",
                  message=f"Running {len(checks)} DQ checks")

    def run_single_check(check):
        """Run a single check and return a dict with results."""
        name = check["name"]
        table = check["table"]
        metric = check["metric"]
        threshold = check["threshold"]
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(jdbc_url, user=jdbc_user, password=jdbc_password)
            cursor = conn.cursor()
            cursor.execute("SET max_parallel_workers_per_gather = 0")
            value = None
            error = None
            passed = False
            alert_threshold_pct = check.get("alert_threshold_pct", 20)
            if metric == "null_rate":
                col = check["column"]
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                total = cursor.fetchone()[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
                nulls = cursor.fetchone()[0]
                value = nulls / max(total, 1)
                passed = value <= threshold
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
                passed = value <= threshold
            elif metric == "row_count_variance":
                expected_min = check.get("expected_min", 0)
                expected_count = check.get("expected_count", 0)
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                if expected_count > 0:
                    value = abs(count - expected_count) / expected_count
                elif expected_min > 0:
                    value = abs(count - expected_min) / expected_min
                else:
                    value = 0.0
                passed = value <= threshold
            if value is None:
                passed = False
            if passed and alert_threshold_pct > 0 and value > (alert_threshold_pct / 100.0):
                passed = False
                cursor.execute(f"""
                    INSERT INTO silver.data_quality_log
                        (check_name, table_name, metric_name, metric_value, threshold, passed, batch_id, logged_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (f"{name}_alert", table, "row_count_deviation",
                      value, alert_threshold_pct / 100.0, False, batch_id))
            # Log the result to the database
            cursor.execute("""
                INSERT INTO silver.data_quality_log
                    (check_name, table_name, metric_name, metric_value, threshold, passed, batch_id, logged_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (name, table, metric, value, threshold, passed, batch_id))
            status = "PASS" if passed else "FAIL"
            conn.commit()
            return {"name": name, "passed": passed, "value": value, "threshold": threshold, "error": None}
        except Exception as e:
            try:
                if conn:
                    conn.rollback()
                if cursor and conn and not conn.closed:
                    cursor.execute("""
                        INSERT INTO silver.quarantine
                            (table_name, check_name, error_message, quarantined_at)
                        VALUES (%s, %s, %s, NOW())
                    """, (table, name, str(e)))
                    conn.commit()
            except Exception:
                pass
            return {"name": name, "passed": False, "value": 0.0, "threshold": threshold, "error": str(e)}
        finally:
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

    all_passed = True
    # Use ThreadPoolExecutor with max_workers=3 (or number of checks, whichever is smaller)
    max_workers = min(3, len(checks))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_check = {executor.submit(run_single_check, check): check for check in checks}
        for future in as_completed(future_to_check):
            result = future.result()
            if not result["passed"]:
                all_passed = False
            status = "PASS" if result["passed"] else "FAIL"
            print(f"[DQ] {status}: {result['name']} = {result['value']:.4f} (threshold: {result['threshold']})")
            if result["error"]:
                print(f"[DQ] ERROR: {result['name']} — {result['error']}")
            log.log_stage(stage="dq_check", batch_id=batch_id,
                          status=status.lower(), row_count=int(result["value"] * 10000),
                          message=f"{result['name']}: {result['value']:.4f} vs {result['threshold']}")

    log.log_stage(stage="dq_runner", batch_id=batch_id,
                  status="complete" if all_passed else "failed",
                  message=f"All checks passed" if all_passed else f"Some checks failed")
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
