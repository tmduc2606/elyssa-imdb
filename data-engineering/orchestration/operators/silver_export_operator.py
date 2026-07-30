import duckdb
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from airflow.models import BaseOperator


class SilverExportOperator(BaseOperator):
    """
    Exports all 14 Silver tables (6 parent + 8 child) from PostgreSQL
    to Snappy Parquet in a bind-mounted host directory.

    The bind mount at /opt/airflow/output/silver/ maps to
    data-science/marts/silver/ on the host, surviving Docker wipes.
    """

    template_fields = ("output_dir",)

    def __init__(
        self,
        pg_host="postgres",
        pg_port=5432,
        pg_db="elyssa_warehouse",
        pg_user="elyssa",
        pg_password_env="GOLD_EXPORT_PG_PASSWORD",
        output_dir="/opt/airflow/output/silver/",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_db = pg_db
        self.pg_user = pg_user
        self.pg_password_env = pg_password_env
        self.output_dir = output_dir

    def execute(self, context):
        pg_password = os.environ.get(self.pg_password_env, "")
        if not pg_password:
            raise ValueError(f"{self.pg_password_env} environment variable is not set")

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        conn = duckdb.connect(":memory:")
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        dsn = f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} user={self.pg_user} password={pg_password}"
        conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'silver');")

        tables = [
            "title_basics", "title_akas", "title_crew", "title_episode",
            "title_principal", "title_rating", "name_basics",
            "title_genre", "title_director", "title_writer",
            "title_akas_type", "title_akas_attribute", "title_principal_char",
            "name_profession", "name_known_for_title",
        ]

        row_counts = {}
        for t in tables:
            path = Path(self.output_dir) / f"{t}.parquet"
            try:
                conn.execute(f'COPY (SELECT * FROM pg."{t}") TO \'{path}\' (FORMAT PARQUET, COMPRESSION SNAPPY)')
                r = conn.execute(f'SELECT count(*) FROM pg."{t}"').fetchone()[0]
                row_counts[t] = r
                self.log.info(f"Exported silver.{t}: {r:,} rows -> {path}")
            except Exception as e:
                row_counts[t] = None
                self.log.warning(f"Failed to export silver.{t}: {e}")

        manifest = {
            "batch_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "row_counts": row_counts,
            "layer": "silver",
            "description": "Silver-layer PostgreSQL tables exported as Parquet for DS benchmarking",
        }
        manifest_path = Path(self.output_dir) / "_MANIFEST.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        self.log.info(f"Manifest written: {manifest_path}")

        conn.close()
