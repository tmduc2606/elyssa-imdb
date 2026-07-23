# Elyssa Full Pipeline Runbook

Sequential 3-day execution on reference hardware (AMD Athlon 200GE, 16 GB RAM).

Memory-hardened compose at `docker/docker-compose.yml` (~5-7 GB peak with all services).

## Day 1 — Data Engineering (5-6 hours)

```powershell
# === PHASE 1: DE Pipeline ===
Write-Host "=== Step 1: Build & Start DE stack ===" -ForegroundColor Cyan
docker builder prune -f
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps

Write-Host "=== Step 2: Download IMDb data ===" -ForegroundColor Cyan
$files = @("title.basics","title.akas","title.ratings","title.episode","title.crew","title.principals","name.basics")
$dest = "data-engineering/duke/gate0/source"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($f in $files) {
    $url = "https://datasets.imdbws.com/$f.tsv.gz"
    $out = "$dest/$f.tsv.gz"
    if (-not (Test-Path $out)) {
        Write-Host "Downloading $f ..."
        Invoke-WebRequest -Uri $url -OutFile $out
    }
}

Write-Host "=== Step 3: Trigger DE pipeline ===" -ForegroundColor Cyan
docker exec elyssa-airflow airflow dags unpause imdb_pipeline -y
docker exec elyssa-airflow airflow dags trigger imdb_pipeline

Write-Host "=== Step 4: Verify DE output ===" -ForegroundColor Cyan
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "SELECT table_name, n_live_tup FROM pg_stat_user_tables WHERE schemaname='gold' ORDER BY table_name;"
Get-ChildItem data-science/marts/full/*.parquet | Select-Object Name, Length
Get-Content data-science/marts/full/_MANIFEST.json
```

## Day 2 — Data Science (3-4 hours)

```powershell
Write-Host "=== Phase 2: Data Science Pipeline ===" -ForegroundColor Cyan
cd data-science
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet

python scripts/run_pipeline.py --stage all
python scripts/validate_contracts.py
```

## Day 3 — Web Application (15 min)

```powershell
Write-Host "=== Phase 3: Web Application ===" -ForegroundColor Cyan
cd web-application/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000 &

cd ../client
npm install --silent
npm run dev &

Start-Sleep -Seconds 5
curl http://localhost:8000/health
python -m pytest tests/ -q
```
