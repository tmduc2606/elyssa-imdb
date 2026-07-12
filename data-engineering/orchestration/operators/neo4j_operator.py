from airflow.models import BaseOperator
from typing import List
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


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
        sync_script: str = "/opt/airflow/data-engineering/scripts/neo4j_sync.py",
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

        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        log.log_stage(stage="neo4j_sync", batch_id=batch_id, status="started",
                      message=f"Syncing {len(self.tables_to_sync)} tables to Neo4j")

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
        elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
        if result.returncode != 0:
            self.log.error(f"Neo4j sync failed: {result.stderr}")
            log.log_error(stage="neo4j_sync", batch_id=batch_id,
                          error=f"Neo4j sync failed: {result.stderr[-500:]}")
            raise RuntimeError(f"Neo4j sync failed: {result.stderr}")
        self.log.info(f"Neo4j sync completed: {result.stdout[:500]}")
        log.log_stage(stage="neo4j_sync", batch_id=batch_id,
                      status="complete", duration_ms=elapsed,
                      message=f"Synced {len(self.tables_to_sync)} tables")
