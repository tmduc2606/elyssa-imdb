import duckdb
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from airflow.models import BaseOperator

class GoldExportOperator(BaseOperator):
    def __init__(
        self,
        pg_host="postgres",
        pg_port=5432,
        pg_db="elyssa_warehouse",
        pg_user="elyssa",
        pg_password_env="GOLD_EXPORT_PG_PASSWORD",
        output_dir="/opt/airflow/output/gold/",
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
        conn = duckdb.connect(':memory:')
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        dsn = f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} user={self.pg_user} password={pg_password}"
        conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'gold');")

        tables = ['dim_person', 'dim_title', 'fact_episode', 'fact_performance', 'fact_title_principal', 'fact_title_rating']
        row_counts = {}
        for t in tables:
            path = Path(self.output_dir) / f"{t}.parquet"
            if t == 'dim_title':
                conn.execute(f"""
                    COPY (
                        SELECT * FROM pg.gold."{t}"
                        WHERE NOT (title_type = 'movie' AND (runtime_minutes IS NULL OR runtime_minutes <= 0))
                    ) TO '{path}' (FORMAT PARQUET, COMPRESSION SNAPPY)
                """)
            else:
                conn.execute(f'COPY (SELECT * FROM pg.gold."{t}") TO \'{path}\' (FORMAT PARQUET, COMPRESSION SNAPPY)')
            r = conn.execute(f'SELECT count(*) FROM pg.gold."{t}"').fetchone()[0]
            row_counts[t] = r
            self.log.info(f"Exported {t}: {r:,} rows -> {path}")

        manifest = {
            "batch_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "row_counts": row_counts,
        }
        manifest_path = Path(self.output_dir) / "_MANIFEST.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        self.log.info(f"Manifest written: {manifest_path}")

        conn.close()
