#!/usr/bin/env bash
# Elyssa-IMDb | Airflow Entrypoint Wrapper
#
# Pre-creates the simple_auth_manager password file so Airflow 3's
# `airflow standalone` uses a known password (admin/admin) instead of
# generating a random one. Then delegates to the original /entrypoint.
#
# Airflow 3 with simple_auth_manager stores the admin password at:
#   $AIRFLOW_HOME/simple_auth_manager_passwords.json.generated
# If this file exists when standalone runs, it skips generation.

set -euo pipefail

AIRFLOW_HOME="${AIRFLOW_HOME:-/opt/airflow}"
PASSWORD_FILE="${AIRFLOW_HOME}/simple_auth_manager_passwords.json.generated"

# Only pre-seed if the file doesn't exist yet (first start).
if [[ ! -f "${PASSWORD_FILE}" ]]; then
    ADMIN_USER="${AIRFLOW_ADMIN_USER:-admin}"
    ADMIN_PASS="${AIRFLOW_ADMIN_PASSWORD:-admin}"
    echo "{\"${ADMIN_USER}\": \"${ADMIN_PASS}\"}" > "${PASSWORD_FILE}"
    echo "[INFO] Pre-seeded simple_auth_manager password for '${ADMIN_USER}'"
fi

# Fix volume permissions (Docker named volumes are mounted as root).
# The tmp/spill directory must be writable by the airflow user.
TMP_DIR="${AIRFLOW_HOME}/output/tmp"
if [[ -d "${TMP_DIR}" ]]; then
    chmod 777 "${TMP_DIR}"
    echo "[INFO] Fixed permissions on ${TMP_DIR}"
fi

# Delegate to the original Airflow entrypoint.
exec /entrypoint "${@}"
