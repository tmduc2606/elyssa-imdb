"""
Neo4j Graph Sync — Syncs Silver PostgreSQL tables to Neo4j.

Merges node tables (fast with UNIQUE constraints), creates relationships
(CREATE, ~100x faster than MERGE on 12M+ existing edges). Duplicate
relationships are cleaned up post-sync via a dedup query.
"""

import argparse
import time

BATCH_SIZE = 500
BATCH_SIZE_RELS = 300
MAX_RETRIES = 3
RETRY_DELAY_S = 5

CYPHER_SCHEMA = """
CREATE CONSTRAINT IF NOT EXISTS FOR (t:Title) REQUIRE t.tconst IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.nconst IS UNIQUE;
CREATE INDEX IF NOT EXISTS FOR (t:Title) ON (t.title_type);
CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.primary_name);
"""

CYPHER_SYNC_TITLE = """
UNWIND $batch AS row
MERGE (t:Title {tconst: row.tconst})
SET t.primary_title = row.primary_title,
    t.title_type = row.title_type,
    t.start_year = row.start_year,
    t.end_year = row.end_year,
    t.runtime_minutes = row.runtime_minutes,
    t.is_adult = row.is_adult,
    t.average_rating = row.average_rating,
    t.num_votes = row.num_votes,
    t.updated_at = datetime()
"""

CYPHER_SYNC_PERSON = """
UNWIND $batch AS row
MERGE (p:Person {nconst: row.nconst})
SET p.primary_name = row.primary_name,
    p.birth_year = row.birth_year,
    p.death_year = row.death_year,
    p.updated_at = datetime()
"""

CYPHER_DEDUP = """
MATCH (p:Person)-[r:ACTED_IN]->(t:Title)
WITH p, t, collect(r) AS rels
WHERE size(rels) > 1
UNWIND tail(rels) AS dup
DELETE dup
"""

CYPHER_SYNC_ACTED_IN = """
UNWIND $batch AS row
MATCH (p:Person {nconst: row.nconst})
MATCH (t:Title {tconst: row.tconst})
CREATE (p)-[r:ACTED_IN]->(t)
SET r.category = row.category,
    r.job = row.job,
    r.characters = row.characters
"""


def run_with_retry(session, cypher, batch, table_name):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            session.run(cypher, batch=batch)
            return
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"[Neo4j] Retry {attempt}/{MAX_RETRIES} for {table_name} "
                      f"batch of {len(batch)}: {e}")
                time.sleep(RETRY_DELAY_S * attempt)
            else:
                raise


def sync_table(uri, user, password, table_name):
    from neo4j import GraphDatabase
    import psycopg2
    import psycopg2.extras
    from decimal import Decimal

    def _convert_row(row: dict) -> dict:
        return {
            k: float(v) if isinstance(v, Decimal) else v
            for k, v in row.items()
        }

    TABLE_QUERIES = {
        "title_basics": """
            SELECT t.tconst, t.primary_title, t.title_type,
                   t.start_year, t.end_year, t.runtime_minutes,
                   t.is_adult,
                   r.average_rating, r.num_votes
            FROM silver.title_basics t
            LEFT JOIN silver.title_rating r ON t.tconst = r.tconst
            WHERE t.is_current = TRUE
        """,
        "name_basics": """
            SELECT n.nconst, n.primary_name, n.birth_year, n.death_year
            FROM silver.name_basics n
            WHERE n.is_current = TRUE
        """,
        "title_principal": """
            SELECT p.tconst, p.nconst, p.category, p.job,
                   pc.character_name
            FROM silver.title_principal p
            LEFT JOIN silver.title_principal_char pc
                ON p.tconst = pc.tconst AND p.ordering = pc.ordering
        """,
    }

    if table_name not in TABLE_QUERIES:
        print(f"[Neo4j] Unknown table: {table_name}")
        return

    CYPHER_MAP = {
        "title_basics": CYPHER_SYNC_TITLE,
        "name_basics": CYPHER_SYNC_PERSON,
        "title_principal": CYPHER_SYNC_ACTED_IN,
    }

    batch_size = BATCH_SIZE_RELS if table_name == "title_principal" else BATCH_SIZE

    pg_conn = psycopg2.connect(
        host="postgres", port=5432, dbname="elyssa_warehouse",
        user="elyssa", password="elyssa_pg_2026"
    )
    try:
        with pg_conn.cursor(name=f"neo4j_sync_{table_name}", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.itersize = batch_size
            cur.execute(TABLE_QUERIES[table_name])
            batch = []
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                total_synced = 0
                for row in cur:
                    batch.append(_convert_row(dict(row)))
                    if len(batch) >= batch_size:
                        run_with_retry(session, CYPHER_MAP[table_name], batch, table_name)
                        total_synced += len(batch)
                        print(f"[Neo4j] {table_name}: {total_synced:,} rows synced", end="\r")
                        batch = []
                if batch:
                    run_with_retry(session, CYPHER_MAP[table_name], batch, table_name)
                    total_synced += len(batch)
            print(f"\n[Neo4j] {table_name}: {total_synced:,} total rows synced")
            driver.close()
    finally:
        pg_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Neo4j Sync Runner")
    parser.add_argument("--uri", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--tables", help="Comma-separated table names")
    args = parser.parse_args()

    tables = args.tables.split(",") if args.tables else []

    from neo4j import GraphDatabase

    # Schema (uses tmp connection, closes after)
    _schema_driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    with _schema_driver.session() as session:
        for stmt in CYPHER_SCHEMA.strip().split(";"):
            if stmt.strip():
                try:
                    session.run(stmt.strip())
                except Exception as e:
                    print(f"[Neo4j] Schema note: {e}")
    _schema_driver.close()

    for table in tables:
        if table.strip():
            sync_table(args.uri, args.user, args.password, table.strip())

    # Dedup any duplicate ACTED_IN relationships (from CREATE on existing data)
    if "title_principal" in tables:
        _dedup_driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        with _dedup_driver.session() as session:
            print("[Neo4j] Deduplicating ACTED_IN relationships...")
            result = session.run(CYPHER_DEDUP)
            stats = result.consume()
            print(f"[Neo4j] Dedup complete: {stats.counters.contains_updates}")
        _dedup_driver.close()


if __name__ == "__main__":
    main()
