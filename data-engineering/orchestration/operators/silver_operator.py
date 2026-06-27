from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults


class SilverTransformOperator(BaseOperator):
    """
    Runs the Silver ETL pipeline: reads Bronze Parquet, transforms,
    and upserts into PostgreSQL.

    Executes silver/etl_runner.py via spark-submit.
    """

    template_fields = ("bronze_path", "jdbc_url")

    @apply_defaults
    def __init__(
        self,
        bronze_path: str = "/data/bronze/",
        jdbc_url: str = "",
        jdbc_user: str = "",
        jdbc_password: str = "",
        spark_master: str = "spark://spark-master:7077",
        spark_app: str = "/opt/spark-apps/silver/etl_runner.py",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.bronze_path = bronze_path
        self.jdbc_url = jdbc_url
        self.jdbc_user = jdbc_user
        self.jdbc_password = jdbc_password
        self.spark_master = spark_master
        self.spark_app = spark_app

    def execute(self, context):
        import subprocess
        cmd = [
            "spark-submit",
            "--master", self.spark_master,
            "--deploy-mode", "client",
            "--jars", "/opt/postgresql-42.7.3.jar",
            self.spark_app,
            "--bronze-path", self.bronze_path,
            "--jdbc-url", self.jdbc_url,
            "--jdbc-user", self.jdbc_user,
            "--jdbc-password", self.jdbc_password,
        ]
        self.log.info(f"Running Silver ETL: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.error(f"Silver ETL failed: {result.stderr}")
            raise RuntimeError(f"Silver ETL failed: {result.stderr}")
        self.log.info(f"Silver ETL completed: {result.stdout[:500]}")
