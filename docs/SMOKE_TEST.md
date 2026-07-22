# Quick Smoke Test (30 minutes)

Verify the entire Elyssa stack works end-to-end without downloading the full IMDb dataset.

## Prerequisites
- Docker Desktop
- Python 3.12+
- Node.js 20+

## Steps

```powershell
# 1. Generate sample data (if not already present)
cd data-science
python scripts/generate_sample_data.py

# 2. Symlink sample data as full data for the quick test
New-Item -ItemType Junction -Path marts\full -Target marts\sample -Force
New-Item -ItemType Junction -Path marts\processed -Target marts\sample_processed -Force
cd ..

# 3. Start API + Frontend
cd web-application/api
.\.venv\Scripts\Activate.ps1
Start-Process powershell -ArgumentList "-NoExit -Command .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
cd ../client
npm install --silent
Start-Process powershell -ArgumentList "-NoExit -Command npm run dev"

# 4. Verify
Start-Sleep -Seconds 5
curl http://localhost:8000/health
curl http://localhost:5173
```

## What gets verified
- Gold Parquet loads in DuckDB
- GraphQL queries return results
- REST endpoints respond
- ML models load and predict
- Frontend renders homepage
