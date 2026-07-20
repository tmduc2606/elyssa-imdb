import duckdb
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GoldDataLoader:
    def __init__(self, marts_dir: Path, development_mode: bool = True,
                 sample_percent: int = 5, random_seed: int = 42):
        self.marts_dir = marts_dir
        self.development_mode = development_mode
        self.sample_percent = sample_percent
        self.random_seed = random_seed
        self.con: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        self.con = duckdb.connect(":memory:")

        tables = {
            "dim_title": "dim_title.parquet",
            "dim_person": "dim_person.parquet",
            "fact_title_rating": "fact_title_rating.parquet",
            "fact_title_principal": "fact_title_principal.parquet",
            "fact_performance": "fact_performance.parquet",
            "fact_episode": "fact_episode.parquet",
        }

        for view_name, parquet_file in tables.items():
            parquet_path = self.marts_dir / parquet_file
            if self.development_mode:
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW {view_name} AS
                    SELECT * FROM read_parquet('{parquet_path}')
                    TABLESAMPLE SYSTEM ({self.sample_percent} PERCENT) REPEATABLE ({self.random_seed})
                """)
            else:
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW {view_name} AS
                    SELECT * FROM read_parquet('{parquet_path}')
                """)

            count = self.con.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
            logger.info(f"Loaded {view_name}: {count:,} rows")

        return self.con

    def query_to_df(self, sql: str, max_rows: int = 50000):
        count_sql = f"SELECT count(*) FROM ({sql}) t"
        row_cnt = self.con.execute(count_sql).fetchone()[0]
        if row_cnt > max_rows:
            raise ValueError(
                f"Query returns {row_cnt:,} rows (limit: {max_rows:,}). "
                "Add aggregation or sampling."
            )
        return self.con.execute(sql).df()

    def close(self):
        if self.con:
            self.con.close()
