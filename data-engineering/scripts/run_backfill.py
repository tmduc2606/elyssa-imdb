"""
Elyssa-IMDb Pipeline — Backfill Runner
Runs the full pipeline using `airflow dags backfill` to bypass the execution API
heartbeat mechanism that kills long-running tasks after ~5 minutes.

Usage:
    pwsh -File scripts/run_backfill.ps1

Prerequisites:
    - Docker Desktop running with WSL2 backend
    - .wslconfig with memory=12GB
"""

import subprocess
import sys
import time
import json
import urllib.request
from datetime import datetime, date


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def wait_for_airflow(max_wait: int = 300) -> bool:
    """Wait for Airflow webserver to be healthy."""
    print("\n[1/5] Waiting for Airflow to be healthy...")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = urllib.request.urlopen("http://localhost:8080/health", timeout=5)
            data = json.loads(resp.read().decode())
            if data.get("metadatabase", {}).get("status") == "healthy":
                print("  Airflow is healthy!")
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def unpause_dag(dag_id: str):
    """Unpause the DAG so backfill can run."""
    print(f"\n[2/5] Unpausing DAG '{dag_id}'...")
    run(["docker", "exec", "elyssa-airflow-webserver",
         "airflow", "dags", "unpause", dag_id])


def run_backfill(dag_id: str, run_date: str):
    """Run backfill for the specified date range."""
    print(f"\n[3/5] Running backfill for DAG '{dag_id}' on {run_date}...")
    print("  This will run tasks sequentially without scheduler heartbeat.")
    print("  Expected time: 60-90 minutes for full pipeline.\n")

    cmd = [
        "docker", "exec", "-e", "AIRFLOW__CORE__DAG_FILE_LOCK_TIMEOUT=3600",
        "elyssa-airflow-webserver",
        "airflow", "dags", "backfill",
        "--start-date", run_date,
        "--end-date", run_date,
        "--reset-dagruns",
        "--verbose",
        dag_id,
    ]
    result = run(cmd, check=False)
    if result.returncode != 0:
        print(f"\n  Backfill failed with return code {result.returncode}")
        print(f"  stderr: {result.stderr[-2000:] if result.stderr else 'N/A'}")
        return False
    print("\n  Backfill completed successfully!")
    return True


def check_results():
    """Check pipeline status after backfill."""
    print("\n[4/5] Checking pipeline results...")
    run(["docker", "exec", "elyssa-airflow-webserver",
         "airflow", "dags", "list-runs", "-d", "imdb_pipeline", "--limit", "1"],
         check=False)


def main():
    dag_id = "imdb_pipeline"
    run_date = date.today().isoformat()

    print("=" * 60)
    print("Elyssa-IMDb Pipeline — Backfill Runner")
    print(f"  DAG: {dag_id}")
    print(f"  Date: {run_date}")
    print("=" * 60)

    # Step 1: Wait for Airflow
    if not wait_for_airflow():
        print("\nERROR: Airflow did not become healthy within timeout.")
        sys.exit(1)

    # Step 2: Unpause DAG
    unpause_dag(dag_id)

    # Step 3: Run backfill
    success = run_backfill(dag_id, run_date)

    # Step 4: Check results
    check_results()

    # Step 5: Summary
    print("\n[5/5] Summary")
    if success:
        print("  Pipeline completed successfully!")
        print("  Check Gold output: docker exec elyssa-airflow-webserver ls -la /opt/airflow/output/gold/")
    else:
        print("  Pipeline failed. Check logs:")
        print("    docker logs elyssa-airflow-webserver --tail 100")

    print("\n" + "=" * 60)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
