file_path = 'data-engineering/dq/run_checks.py'

with open(file_path, 'r') as f:
    lines = f.readlines()

# Find start of def run_checks
start = -1
for i, line in enumerate(lines):
    if line.strip().startswith('def run_checks'):
        start = i
        break

if start == -1:
    print("Function not found")
    exit(1)

# Find end (next def or end of file)
end = len(lines)
for i in range(start + 1, len(lines)):
    if lines[i].strip().startswith('def '):
        end = i
        break

# New function lines (each line ends with newline)
new_func = '''def run_checks(config_path: str, jdbc_url: str, jdbc_user: str, jdbc_password: str):
    """
    Data Quality Check Runner

    Reads DQ config, executes checks against Silver PostgreSQL,
    and logs results to silver.data_quality_log and silver.quarantine.
    This version runs checks in parallel using a ThreadPoolExecutor.
    """
    import psycopg2
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime, timezone

    log = get_logger()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if config_path:
        with open(config_path) as f:
            checks = yaml.safe_load(f).get("checks", [])
    else:
        checks = DEFAULT_CHECKS

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
            passed = False
            error = None
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
            else:
                return {"name": name, "passed": False, "value": 0.0, "threshold": threshold, "error": "Unknown metric"}
            if metric != "row_count_variance":
                passed = value <= threshold
            # Log the result to the database
            cursor.execute("""
                INSERT INTO silver.data_quality_log
                    (check_name, table_name, metric_name, metric_value, threshold, passed, batch_id, logged_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (name, table, metric, value, threshold, passed, None))
            status = "PASS" if passed else "FAIL"
            # We will return the result for logging/printing in the main thread
            return {"name": name, "passed": passed, "value": value, "threshold": threshold, "error": None}
        except Exception as e:
            if conn:
                conn.rollback()
            if cursor:
                cursor.execute("""
                    INSERT INTO silver.quarantine
                        (table_name, check_name, error_message, quarantined_at)
                    VALUES (%s, %s, %s, NOW())
                """, (table, name, str(e)))
            return {"name": name, "passed": False, "value": 0.0, "threshold": threshold, "error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

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
'''

# Ensure each line ends with newline (the triple-quoted string already has newlines)
# But we need to split into lines and ensure each line ends with \n
new_lines = new_func.splitlines(keepends=True)  # This keeps the newline characters

# Replace
new_lines_all = lines[:start] + new_lines + lines[end:]

with open(file_path, 'w') as f:
    f.writelines(new_lines_all)

print("Successfully replaced run_checks function.")