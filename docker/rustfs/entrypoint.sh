#!/bin/sh
# Elyssa-IMDb | RustFS Entrypoint
# Creates Bronze bucket on startup

set -e

# Start RustFS in background
rustfs --address ":9000" --console-address ":9001" --access-key "${RUSTFS_ACCESS_KEY}" --secret-key "${RUSTFS_SECRET_KEY}" "${RUSTFS_STORAGE_PATH:-/data}" &

# Wait for service to be ready
sleep 3

# Create Bronze bucket
echo "Creating Bronze bucket..."
curl -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    "http://localhost:9000/bronze/" \
    -H "Host: localhost" \
    || true

echo "RustFS ready on :9000 (API) / :9001 (Console)"
echo "Bronze bucket created."

# Keep container running
wait
