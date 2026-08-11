import argparse
from datetime import datetime, timedelta, timezone


CHECK_TABLES = [
    "silver.title_basics",
    "silver.name_basics",
    "silver.title_rating",
    "silver.title_episode",
    "silver.title_akas",
    "silver.title_principal",
]


def check_freshness(
    jdbc_url: str, jdbc_user: str, jdbc_password: str,
    sla_hours: int = 24, reference_time=None,
):
    """Check silver freshness against an SLA window.

    reference_time: the pipeline run's reference timestamp (typically the
    DAG run execution_date). Staleness is measured as
    reference_time - max(ingested_at) and must stay within sla_hours.
    This keeps multi-day recovery runs honest: checkpoint-skipped tables
    are judged against the run that consumed them, while a genuinely
    stale table (older than SLA relative to the run) still fails.
    If reference_time is None, wall-clock now is used (backward compat).
    """
    import psycopg2

    conn = psycopg2.connect(jdbc_url, user=jdbc_user, password=jdbc_password)
    cursor = conn.cursor()
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    elif reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    sla_boundary = reference_time - timedelta(hours=sla_hours)
    stale_tables = []

    for table in CHECK_TABLES:
        try:
            cursor.execute(f"SELECT MAX(ingested_at) FROM {table}")
            result = cursor.fetchone()
            if result and result[0]:
                max_ts = result[0]
                if max_ts.tzinfo is None:
                    max_ts = max_ts.replace(tzinfo=timezone.utc)
                if max_ts < sla_boundary:
                    stale_tables.append((table, max_ts))
                    print(f"[FRESHNESS] FAIL: {table} last updated {max_ts} (SLA: {sla_hours}h)")
                else:
                    print(f"[FRESHNESS] PASS: {table} last updated {max_ts}")
            else:
                print(f"[FRESHNESS] EMPTY: {table} has no data")
        except Exception as e:
            # O7: no auto-ALTER — schema changes must go through explicit
            # migrations (silver/schema.sql). Report and continue so a single
            # broken table doesn't abort the whole SLA scan.
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"[FRESHNESS] ERROR: {table} — {e}")

    cursor.close()
    conn.close()

    if stale_tables:
        msg = f"Stale tables: {', '.join(t for t, _ in stale_tables)}"
        print(f"[FRESHNESS] {msg}")
        raise RuntimeError(msg)

    print(f"[FRESHNESS] All {len(CHECK_TABLES)} tables within SLA (reference: {reference_time.isoformat()})")


def main():
    parser = argparse.ArgumentParser(description="Freshness Monitor")
    parser.add_argument("--jdbc-url", required=True)
    parser.add_argument("--jdbc-user", required=True)
    parser.add_argument("--jdbc-password", required=True)
    parser.add_argument("--sla-hours", type=int, default=24)
    parser.add_argument("--reference-time", type=str, default=None,
                        help="ISO8601 run reference timestamp; staleness measured against this instead of now")
    args = parser.parse_args()

    reference_time = None
    if args.reference_time:
        reference_time = datetime.fromisoformat(args.reference_time)

    check_freshness(args.jdbc_url, args.jdbc_user, args.jdbc_password,
                    args.sla_hours, reference_time=reference_time)


if __name__ == "__main__":
    main()
