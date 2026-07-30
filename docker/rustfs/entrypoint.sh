#!/bin/sh
set -e
rustfs --address ":9000" --console-address ":9001" --access-key "${RUSTFS_ACCESS_KEY}" --secret-key "${RUSTFS_SECRET_KEY}" "${RUSTFS_STORAGE_PATH:-/data}" &
sleep 3
for bucket in imdb-source bronze gold-exports; do
  echo "Creating bucket: $bucket"
  curl -s -o /dev/null -w "%{http_code}" -X PUT "http://localhost:9000/${bucket}/" || true
done
echo "RustFS ready on :9000 (API) / :9001 (Console)"
echo "Buckets created: imdb-source, bronze, gold-exports"
wait
