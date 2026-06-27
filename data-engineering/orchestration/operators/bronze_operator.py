from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import List


class BronzeIngestOperator(BaseOperator):
    """
    Triggers PySpark bronze ingestion for specified source tables.

    Submits a spark-submit job for bronze/ingest_imdb.py with the
    given source tables and bronze output path.
    """

    template_fields = ("bronze_path",)

    @apply_defaults
    def __init__(
        self,
        source_tables: List[str],
        bronze_path: str = "/data/bronze/",
        spark_master: str = "spark://spark-master:7077",
        spark_app: str = "/opt/spark-apps/bronze/ingest_imdb.py",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.source_tables = source_tables
        self.bronze_path = bronze_path
        self.spark_master = spark_master
        self.spark_app = spark_app

    def execute(self, context):
        import subprocess
        tables_arg = ",".join(self.source_tables)
        cmd = [
            "spark-submit",
            "--master", self.spark_master,
            "--deploy-mode", "client",
            self.spark_app,
            "--tables", tables_arg,
            "--output", self.bronze_path,
        ]
        self.log.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.error(f"Spark submit failed: {result.stderr}")
            raise RuntimeError(f"Bronze ingestion failed: {result.stderr}")
        self.log.info(f"Bronze ingestion completed: {result.stdout[:500]}")
