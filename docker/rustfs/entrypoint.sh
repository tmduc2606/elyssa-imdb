#!/bin/sh
set -e
rustfs --address ":9000" --console-address ":9001" --access-key "${RUSTFS_ACCESS_KEY}" --secret-key "${RUSTFS_SECRET_KEY}" "${RUSTFS_STORAGE_PATH:-/data}" &
sleep 3

# Configure rc alias for local S3 access
rc alias set local http://localhost:9000 "${RUSTFS_ACCESS_KEY}" "${RUSTFS_SECRET_KEY}" 2>&1

for bucket in imdb-source bronze gold-exports; do
  echo "Creating bucket: $bucket"
  rc mb "local/${bucket}" 2>&1 || true
done
echo "RustFS ready on :9000 (API) / :9001 (Console)"
echo "Buckets created: imdb-source, bronze, gold-exports"
wait
