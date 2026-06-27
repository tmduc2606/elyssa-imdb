from airflow.models import BaseOperator
from typing import List


class Neo4jSyncOperator(BaseOperator):
    """
    Synchronizes selected Silver tables to Neo4j graph database.

    Executes neo4j/sync_runner.py with table names and connection details.
    """

    template_fields = ("neo4j_uri",)

    def __init__(
        self,
        neo4j_uri: str = "",
        neo4j_user: str = "",
        neo4j_password: str = "",
        tables_to_sync: List[str] = None,
        sync_script: str = "/opt/neo4j/sync_runner.py",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.tables_to_sync = tables_to_sync or []
        self.sync_script = sync_script

    def execute(self, context):
        import subprocess
        import os

        # Resolve sync script path
        sync_script = self.sync_script
        if not os.path.isfile(sync_script):
            alt = "/opt/airflow/data-engineering/scripts/neo4j_sync.py"
            if os.path.isfile(alt):
                sync_script = alt

        tables_arg = ",".join(self.tables_to_sync)
        cmd = [
            "python", sync_script,
            "--uri", self.neo4j_uri,
            "--user", self.neo4j_user,
            "--password", self.neo4j_password,
            "--tables", tables_arg,
        ]
        self.log.info(f"Running Neo4j sync: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.error(f"Neo4j sync failed: {result.stderr}")
            raise RuntimeError(f"Neo4j sync failed: {result.stderr}")
        self.log.info(f"Neo4j sync completed: {result.stdout[:500]}")
