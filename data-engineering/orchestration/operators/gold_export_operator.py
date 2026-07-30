import duckdb
import json
import os
import subprocess
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
        tar_path="/tmp/gold_marts.tar.gz",
        s3_output_prefix="s3://gold-exports/",
        write_s3=False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_db = pg_db
        self.pg_user = pg_user
        self.pg_password_env = pg_password_env
        self.output_dir = output_dir
        self.tar_path = tar_path
        self.s3_output_prefix = s3_output_prefix
        self.write_s3 = write_s3

    def execute(self, context):
        pg_password = os.environ.get(self.pg_password_env, "")
        if not pg_password:
            raise ValueError(f"{self.pg_password_env} environment variable is not set")

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        try:
            import psycopg2
            ck_conn = psycopg2.connect(host=self.pg_host, port=self.pg_port, dbname=self.pg_db, user=self.pg_user, password=pg_password)
            ck_cur = ck_conn.cursor()
            ck_cur.execute("""
                INSERT INTO silver.pipeline_checkpoints (pipeline_name, stage, batch_id, completed_at)
                VALUES ('gold', 'export_pending', %s, NOW())
                ON CONFLICT (pipeline_name, stage)
                DO UPDATE SET batch_id = EXCLUDED.batch_id, completed_at = NOW()
            """, (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),))
            ck_conn.commit()
            ck_cur.close()
            ck_conn.close()
        except Exception as e:
            self.log.warning(f"Could not write gold checkpoint: {e}")

        conn = duckdb.connect(':memory:')
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        sys.path.insert(0, "/opt/airflow/data-engineering")
        from bronze.s3_config import configure_s3
        configure_s3(conn)
        dsn = f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} user={self.pg_user} password={pg_password}"
        conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'gold');")

        tables = ['dim_person', 'dim_title', 'fact_episode', 'fact_performance', 'fact_title_principal', 'fact_title_rating']
        row_counts = {}
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        for t in tables:
            local_path = Path(self.output_dir) / f"{t}.parquet"
            dim_filter = (
                f" WHERE NOT (title_type = 'movie' AND (runtime_minutes IS NULL OR runtime_minutes <= 0))"
                if t == "dim_title" else ""
            )
            sql = f'SELECT * FROM pg.gold."{t}"{dim_filter}'
            # Local bind mount (primary)
            conn.execute(f"COPY ({sql}) TO '{local_path}' (FORMAT PARQUET, COMPRESSION SNAPPY)")
            r = conn.execute(f'SELECT count(*) FROM pg.gold."{t}"{dim_filter}').fetchone()[0]
            row_counts[t] = r
            self.log.info(f"Exported {t}: {r:,} rows -> {local_path}")
            # Optional S3 write
            if self.write_s3:
                s3_path = f"{self.s3_output_prefix}{batch_id}/{t}.parquet"
                try:
                    conn.execute(f"COPY ({sql}) TO '{s3_path}' (FORMAT PARQUET, COMPRESSION SNAPPY)")
                    self.log.info(f"Exported {t}: {r:,} rows -> {s3_path}")
                except Exception as e:
                    self.log.warning(f"S3 export failed for {t}: {e}")

        manifest = {
            "batch_id": batch_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "row_counts": row_counts,
        }
        manifest_path = Path(self.output_dir) / "_MANIFEST.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        self.log.info(f"Manifest written: {manifest_path}")

        conn.close()

        tar_path = self.tar_path
        files = [f"{t}.parquet" for t in tables] + ["_MANIFEST.json"]
        subprocess.run(
            ["tar", "-czf", tar_path, "-C", self.output_dir] + files,
            check=True, capture_output=True, text=True,
        )
        tar_size = os.path.getsize(tar_path)
        self.log.info(f"Tar archive created: {tar_path} ({tar_size / (1024*1024):.1f} MB)")

        try:
            import psycopg2
            ck_conn = psycopg2.connect(host=self.pg_host, port=self.pg_port, dbname=self.pg_db, user=self.pg_user, password=pg_password)
            ck_cur = ck_conn.cursor()
            total_rows = sum(row_counts.values())
            ck_cur.execute("""
                INSERT INTO silver.pipeline_checkpoints (pipeline_name, stage, batch_id, completed_at, metadata)
                VALUES ('gold', 'export_done', %s, NOW(), %s)
                ON CONFLICT (pipeline_name, stage)
                DO UPDATE SET batch_id = EXCLUDED.batch_id, completed_at = NOW(), metadata = EXCLUDED.metadata
            """, (manifest["batch_id"], json.dumps({"total_rows": total_rows, "tar_path": tar_path, "tar_size_mb": round(tar_size / (1024*1024), 1)})))
            ck_conn.commit()
            ck_cur.close()
            ck_conn.close()
            self.log.info(f"[CHECKPOINT] gold export_done saved ({total_rows:,} total rows)")
        except Exception as e:
            self.log.warning(f"Could not update gold checkpoint: {e}")
