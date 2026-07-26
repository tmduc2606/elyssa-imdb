# Elyssa-IMDb Pipeline — Full Clean Rebuild + Backfill
# This script cleans Docker completely, rebuilds all images, and runs the pipeline via backfill.
#
# Usage:
#   pwsh -File scripts/full_rebuild_and_backfill.ps1

$ErrorActionPreference = "Stop"

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Elyssa-IMDb Pipeline — Full Clean Rebuild + Backfill" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# Step 1: Stop and remove everything
Write-Host "`n[1/6] Stopping all containers..." -ForegroundColor Yellow
docker compose -f docker/docker-compose.yml down --remove-orphans --volumes 2>$null

Write-Host "[2/6] Removing all images..." -ForegroundColor Yellow
$images = docker images -q 2>$null
if ($images) {
    docker rmi -f $images 2>$null
    Write-Host "  Removed all images"
} else {
    Write-Host "  No images to remove"
}

Write-Host "[3/6] Cleaning build cache..." -ForegroundColor Yellow
docker builder prune -af 2>$null
Write-Host "  Build cache cleaned"

Write-Host "[4/6] Pruning Docker system..." -ForegroundColor Yellow
docker system prune -af --volumes 2>$null
Write-Host "  Docker system pruned"

# Step 2: Show Docker status
Write-Host "`n[5/6] Docker status after cleanup:" -ForegroundColor Yellow
docker system df

# Step 3: Rebuild and start
Write-Host "`n[6/6] Rebuilding and starting services..." -ForegroundColor Yellow
Write-Host "  This will take 10-15 minutes for initial build." -ForegroundColor Gray
Write-Host "  Subsequent starts will be much faster (layer cache)." -ForegroundColor Gray

Push-Location docker
try {
    docker compose build --no-cache
    docker compose up -d
} finally {
    Pop-Location
}

Write-Host "`nServices started. Waiting for Airflow to initialize..." -ForegroundColor Green

# Wait for Airflow to be healthy
$maxWait = 300
$elapsed = 0
while ($elapsed -lt $maxWait) {
    try {
        $health = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 5 -UseBasicParsing
        $data = $health.Content | ConvertFrom-Json
        if ($data.metadatabase.status -eq "healthy") {
            Write-Host "  Airflow is healthy!" -ForegroundColor Green
            break
        }
    } catch {
        # Not ready yet
    }
    Start-Sleep -Seconds 5
    $elapsed += 5
    Write-Host "  Waiting... ($elapsed/$maxWait seconds)" -ForegroundColor Gray
}

if ($elapsed -ge $maxWait) {
    Write-Host "  WARNING: Airflow did not become healthy within timeout." -ForegroundColor Red
    Write-Host "  Check logs: docker logs elyssa-airflow-webserver --tail 50" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nRunning backfill pipeline..." -ForegroundColor Green
Write-Host "  Expected time: 60-90 minutes" -ForegroundColor Gray
Write-Host "  Monitor: docker logs -f elyssa-airflow-webserver" -ForegroundColor Gray

# Run backfill
python data-engineering/scripts/run_backfill.py

Write-Host "`nPipeline complete!" -ForegroundColor Green
Write-Host "Check results: docker exec elyssa-airflow-webserver ls -la /opt/airflow/output/gold/" -ForegroundColor Cyan
