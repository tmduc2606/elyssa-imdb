"""Centralized secret resolution for DAGs, operators, and scripts (C1-C7).

Resolves credentials in priority order:
1. Environment variables (set by docker/docker-compose.yml from docker/.env)
2. Airflow Connections (if Airflow is installed and a connection named
   `elyssa_warehouse` exists)

Never falls back to hardcoded plaintext values. Raises RuntimeError with a
clear message so misconfiguration fails loudly instead of silently using a
default secret.
"""

import os


def _get_env(*names: str) -> str:
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return ""


def _get_airflow_connection() -> dict:
    """Return conn params for Airflow Connection 'elyssa_warehouse', or {}."""
    try:
        from airflow.hooks.base import BaseHook  # noqa: PLC0415

        conn = BaseHook.get_connection("elyssa_warehouse")
        return {
            "host": conn.host,
            "port": conn.port,
            "user": conn.login,
            "password": conn.password,
            "dbname": conn.schema,
        }
    except Exception:
        return {}


def pg_user() -> str:
    return _get_env("ELYSSA_PG_USER", "POSTGRES_USER") or "elyssa"


def pg_host() -> str:
    return _get_env("ELYSSA_PG_HOST", "POSTGRES_HOST") or "postgres"


def pg_port() -> int:
    try:
        return int(_get_env("ELYSSA_PG_PORT", "POSTGRES_PORT") or 5432)
    except ValueError:
        return 5432


def pg_db() -> str:
    return _get_env("ELYSSA_PG_DB", "POSTGRES_DB") or "elyssa_warehouse"


def pg_password() -> str:
    env = _get_env("ELYSSA_PG_PASSWORD", "POSTGRES_PASSWORD", "GOLD_EXPORT_PG_PASSWORD")
    if env:
        return env
    conn = _get_airflow_connection()
    if conn.get("password"):
        return conn["password"]
    raise RuntimeError(
        "PostgreSQL password is not configured. Set ELYSSA_PG_PASSWORD (or "
        "POSTGRES_PASSWORD) in the environment via docker/.env, or register an "
        "Airflow Connection named 'elyssa_warehouse'."
    )


def pg_connect_kwargs() -> dict:
    """psycopg2.connect(**kwargs) params resolved from env/Connection."""
    conn = _get_airflow_connection()
    if conn.get("password"):
        return conn
    return {
        "host": pg_host(),
        "port": pg_port(),
        "user": pg_user(),
        "password": pg_password(),
        "dbname": pg_db(),
    }


def s3_access_key() -> str:
    return _get_env("S3_ACCESS_KEY") or "elyssa"


def s3_secret_key() -> str:
    env = _get_env("S3_SECRET_KEY", "RUSTFS_SECRET_KEY")
    if env:
        return env
    raise RuntimeError(
        "S3 secret key is not configured. Set S3_SECRET_KEY in the environment "
        "via docker/.env."
    )
