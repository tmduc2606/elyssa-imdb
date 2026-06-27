"""
Neo4j Graph Sync — Syncs Silver PostgreSQL tables to Neo4j.

Creates nodes for titles, persons, and relationships for cast/crew.
Uses MERGE for idempotency and batch processing.
"""

import argparse
from datetime import datetime

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

CYPHER_SYNC_ACTED_IN = """
UNWIND $batch AS row
MATCH (p:Person {nconst: row.nconst})
MATCH (t:Title {tconst: row.tconst})
MERGE (p)-[r:ACTED_IN]->(t)
SET r.category = row.category,
    r.job = row.job,
    r.characters = row.characters
"""


def sync_table(uri, user, password, table_name):
    from neo4j import GraphDatabase
    import psycopg2
    import psycopg2.extras

    # Map table_name to source query
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

    # Read data from PostgreSQL
    pg_conn = psycopg2.connect(
        host="postgres", port=5432, dbname="elyssa_warehouse",
        user="elyssa", password="elyssa_pg_2026"
    )
    batches = []
    with pg_conn.cursor(name=f"neo4j_sync_{table_name}", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.itersize = 5000
        cur.execute(TABLE_QUERIES[table_name])
        batch = []
        for row in cur:
            batch.append(dict(row))
            if len(batch) >= 5000:
                batches.append(batch)
                batch = []
        if batch:
            batches.append(batch)
    pg_conn.close()

    # Write to Neo4j via MERGE
    driver = GraphDatabase.driver(uri, auth=(user, password))
    cypher_map = {
        "title_basics": CYPHER_SYNC_TITLE,
        "name_basics": CYPHER_SYNC_PERSON,
        "title_principal": CYPHER_SYNC_ACTED_IN,
    }
    cypher = cypher_map[table_name]

    with driver.session() as session:
        total_synced = 0
        for batch in batches:
            session.run(cypher, batch=batch)
            total_synced += len(batch)

    driver.close()
    print(f"[Neo4j] Synced {total_synced} rows for {table_name}")


def main():
    parser = argparse.ArgumentParser(description="Neo4j Sync Runner")
    parser.add_argument("--uri", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--tables", help="Comma-separated table names")
    args = parser.parse_args()

    tables = args.tables.split(",") if args.tables else []

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    with driver.session() as session:
        for stmt in CYPHER_SCHEMA.strip().split(";"):
            if stmt.strip():
                session.run(stmt.strip())

    driver.close()

    for table in tables:
        sync_table(args.uri, args.user, args.password, table.strip())
        print(f"[Neo4j] Synced {table}")


if __name__ == "__main__":
    main()
