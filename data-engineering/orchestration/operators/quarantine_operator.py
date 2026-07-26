from airflow.models import BaseOperator
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


class QuarantineCheckOperator(BaseOperator):
    """
    Checks the silver.quarantine table for records quarantined during this batch.

    Reads quarantine entries matching the current batch_id and raises an alert
    if any records were rejected. Non-fatal: logs warnings but does not halt
    the pipeline unless the quarantine count exceeds fail_threshold.
    """

    template_fields = ("jdbc_url",)

    def __init__(
        self,
        jdbc_url: str = "postgresql://elyssa:***@postgres:5432/elyssa_warehouse",
        jdbc_user: str = "elyssa",
        jdbc_password: str = "elyssa_pg_2026",
        fail_threshold: int = 1000,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.jdbc_url = jdbc_url
        self.jdbc_user = jdbc_user
        self.jdbc_password = jdbc_password
        self.fail_threshold = fail_threshold

    def execute(self, context):
        import psycopg2

        log = get_logger()

        conn = psycopg2.connect(
            host="postgres", port=5432,
            user=self.jdbc_user, password=self.jdbc_password,
            dbname="elyssa_warehouse",
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Find the most recent batch_id from quarantine (latest bronze run)
        cursor.execute(
            "SELECT batch_id FROM silver.quarantine ORDER BY quarantined_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        batch_id = row[0] if row else datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        log.log_stage(stage="quarantine_check", batch_id=batch_id, status="started",
                      message="Checking quarantine table for rejected records")

        # Count quarantine entries for this batch
        cursor.execute(
            "SELECT COUNT(*), COALESCE(STRING_AGG(DISTINCT check_name, ', '), 'none') "
            "FROM silver.quarantine WHERE batch_id = %s",
            (batch_id,)
        )
        count, check_names = cursor.fetchone()

        # Also count total quarantine entries (all-time)
        cursor.execute("SELECT COUNT(*) FROM silver.quarantine")
        total_quarantined = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        log.log_stage(stage="quarantine_check", batch_id=batch_id,
                      status="complete" if count == 0 else "warning",
                      row_count=count,
                      message=f"Batch {batch_id}: {count} quarantined (threshold: {self.fail_threshold}), "
                              f"total: {total_quarantined}, checks: {check_names}")

        if count > 0:
            self.log.warning(f"QUARANTINE ALERT: {count} records quarantined in batch {batch_id}")
            self.log.warning(f"  Failed checks: {check_names}")

        if count > self.fail_threshold:
            raise RuntimeError(
                f"Quarantine threshold exceeded: {count} > {self.fail_threshold} "
                f"records quarantined in batch {batch_id}"
            )

        return {"batch_id": batch_id, "quarantined_count": count}
