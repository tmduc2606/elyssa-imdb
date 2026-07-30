import argparse
from datetime import datetime, timedelta, timezone


CHECK_TABLES = [
    "silver.title_basics",
    "silver.name_basics",
    "silver.title_rating",
    "silver.title_episode",
    "silver.title_akas",
    "silver.title_director",
    "silver.title_writer",
    "silver.title_principal",
]


def check_freshness(jdbc_url: str, jdbc_user: str, jdbc_password: str, sla_hours: int = 24):
    import psycopg2

    conn = psycopg2.connect(jdbc_url, user=jdbc_user, password=jdbc_password)
    cursor = conn.cursor()
    sla_boundary = datetime.now(timezone.utc) - timedelta(hours=sla_hours)
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
            # Check if ingested_at column is missing; add it if so
            try:
                schema, tbl = table.split('.')
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s AND column_name = 'ingested_at'
                """, (schema, tbl))
                if not cursor.fetchone():
                    print(f"[FRESHNESS] Adding ingested_at column to {table}")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN ingested_at TIMESTAMPTZ DEFAULT NOW()")
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_ingested_at ON {table}(ingested_at)")
                    conn.commit()
                    print(f"[FRESHNESS] Added ingested_at to {table} — re-running check")
                    cursor.execute(f"SELECT MAX(ingested_at) FROM {table}")
                    result = cursor.fetchone()
                    if result and result[0]:
                        print(f"[FRESHNESS] PASS: {table} now has ingested_at")
                    else:
                        print(f"[FRESHNESS] EMPTY: {table} has no data after column add")
                else:
                    print(f"[FRESHNESS] ERROR: {table} — {e}")
            except Exception as e2:
                print(f"[FRESHNESS] ERROR: {table} — failed to patch ingested_at: {e2}")

    cursor.close()
    conn.close()

    if stale_tables:
        msg = f"Stale tables: {', '.join(t for t, _ in stale_tables)}"
        print(f"[FRESHNESS] {msg}")
        raise RuntimeError(msg)

    print(f"[FRESHNESS] All {len(CHECK_TABLES)} tables within SLA")


def main():
    parser = argparse.ArgumentParser(description="Freshness Monitor")
    parser.add_argument("--jdbc-url", required=True)
    parser.add_argument("--jdbc-user", required=True)
    parser.add_argument("--jdbc-password", required=True)
    parser.add_argument("--sla-hours", type=int, default=24)
    args = parser.parse_args()

    check_freshness(args.jdbc_url, args.jdbc_user, args.jdbc_password, args.sla_hours)


if __name__ == "__main__":
    main()
