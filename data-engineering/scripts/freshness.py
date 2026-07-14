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
            print(f"[FRESHNESS] ERROR: {table} — {e}")

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
