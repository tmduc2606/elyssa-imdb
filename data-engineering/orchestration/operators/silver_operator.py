from airflow.models import BaseOperator


class SilverTransformOperator(BaseOperator):
    """
    Runs the Silver ETL pipeline: reads Bronze Parquet, transforms,
    and upserts into PostgreSQL.

    Executes silver/etl_runner.py via spark-submit.
    """

    template_fields = ("bronze_path", "jdbc_url")

    def __init__(
        self,
        bronze_path: str = "/data/bronze/",
        jdbc_url: str = "",
        jdbc_user: str = "",
        jdbc_password: str = "",
        spark_master: str = "local[*]",
        spark_app: str = "/opt/airflow/data-engineering/scripts/etl_runner.py",
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
        import os

        # Set JAVA_HOME if not set
        java_home = os.environ.get("JAVA_HOME", "/usr/lib/jvm/java-17-openjdk-amd64")
        if os.path.isdir(java_home):
            os.environ["JAVA_HOME"] = java_home

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
