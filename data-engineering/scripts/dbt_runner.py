"""
Elyssa-IMDb | DBT Runner (detached subprocess)

Executes a dbt command (run or test) for the Gold layer.

Runs OUTSIDE Airflow's supervisor (spawned with start_new_session=True)
so the dbt subprocess is not killed by the scheduler's 300s orphan-pass reset.

The script performs the same setup as DbtRunOperator:
  - Acquires file lock to prevent concurrent runs
  - Kills stale dbt processes
  - Cleans dbt artifacts (target dir)
  - Runs dbt deps if needed
Then runs the dbt command via subprocess.Popen in a new session.

Writes markers to the project directory:
  .dbt.{command}.running   - started
  .dbt.{command}.completed - succeeded
  .dbt.{command}.failed    - failed (check the log)

Usage:
  python dbt_runner.py --project-dir /opt/airflow/data-engineering/gold \
                       --target prod \
                       --command run
"""

import argparse
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

DBT_LOCK_FILE = "/tmp/dbt_lock"


def _log(message: str):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="DBT runner (detached)")
    parser.add_argument("--project-dir", required=True, help="DBT project directory")
    parser.add_argument("--target", default="prod", help="DBT target")
    parser.add_argument(
        "--command",
        required=True,
        choices=["run", "test"],
        help="DBT command to run",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    if not project_dir.is_dir():
        _log(f"FATAL: Project directory does not exist: {project_dir}")
        return 1

    target_dir = project_dir / "target"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine marker names
    run_marker_base = f".dbt.{args.command}"
    running_marker = project_dir / f"{run_marker_base}.running"
    completed_marker = project_dir / f"{run_marker_base}.completed"
    failed_marker = project_dir / f"{run_marker_base}.failed"

    # Clean up any stale markers from previous runs
    for marker in (completed_marker, failed_marker):
        if marker.exists():
            try:
                marker.unlink()
            except OSError:
                pass

    # Acquire lock to prevent concurrent dbt runs
    try:
        lock_fd = os.open(DBT_LOCK_FILE, os.O_CREAT | os.O_WRONLY, 0o666)
        import fcntl

        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError) as e:
        _log(f"FATAL: Unable to acquire lock ({DBT_LOCK_FILE}): {e}")
        return 1

    try:
        # Kill any stale dbt processes (pattern excludes this runner itself:
        # its own cmdline contains "dbt_runner.py", which would match "dbt")
        try:
            result = subprocess.run(
                ["pgrep", "-f", "dbt (run|test|deps|compile)"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split()
                _log(f"Killing stale dbt processes: {pids}")
                subprocess.run(["kill", "-9"] + pids, capture_output=True, timeout=5)
        except Exception:
            pass  # Non-fatal

        # Clean dbt artifacts (target dir)
        try:
            if target_dir.exists():
                for item in target_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    else:
                        shutil.rmtree(item)
        except Exception as e:
            _log(f"Warning: failed to clean dbt target dir: {e}")

        # Check if deps are needed
        deps_dir = project_dir / "dbt_packages"
        deps_file = project_dir / "packages.yml"
        if deps_file.is_file() and (not deps_dir.exists() or not any(deps_dir.iterdir())):
            _log("Running dbt deps (packages missing)")
            deps_cmd = [
                "dbt",
                "deps",
                "--project-dir",
                str(project_dir),
                "--profiles-dir",
                str(project_dir),
            ]
            deps_result = subprocess.run(
                deps_cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if deps_result.returncode != 0:
                _log(f"FATAL: dbt deps failed: {deps_result.stderr}")
                return 1
            _log("dbt deps succeeded")

        # Build dbt command
        cmd = [
            "dbt",
            args.command,
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir),
            "--target",
            args.target,
            "--no-partial-parse",
        ]
        if args.command == "run":
            cmd.append("--full-refresh")

        _log(f"Running: {' '.join(cmd)}")
        start_time = datetime.now(timezone.utc)

        # Open log file for stdout/stderr
        log_path = project_dir / f"dbt_{args.command}.log"
        with open(log_path, "w") as log_file:
            # Write start marker
            with open(running_marker, "w") as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()}\n")

            # Start subprocess
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            _log(f"Started dbt {args.command} with PID {proc.pid}")

            # Wait for completion
            stdout, stderr = proc.communicate()
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Remove running marker
            try:
                if os.path.exists(running_marker):
                    os.remove(running_marker)
            except OSError:
                pass

            if proc.returncode != 0:
                _log(f"FAILED: dbt {args.command} returned {proc.returncode} after {elapsed:.0f}s")
                # Truncate tail for logging
                try:
                    with open(log_path, "r") as f:
                        lines = f.readlines()
                        tail = "".join(lines[-20:]) if len(lines) > 20 else "".join(f.readlines())
                except Exception:
                    tail = "(unable to read log)"
                _log(f"Tail of log: {tail}")
                failed_marker.touch()
                return 1
            else:
                _log(f"SUCCESS: dbt {args.command} completed in {elapsed:.0f}s")
                # Write a short tail to the log for visibility
                try:
                    with open(log_path, "r") as f:
                        lines = f.readlines()
                        tail = "".join(lines[-10:]) if len(lines) > 10 else "".join(f.readlines())
                except Exception:
                    tail = "(log empty)"
                _log(f"Tail of log: {tail}")
                completed_marker.touch()
                return 0
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(lock_fd)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())