# Elyssa-IMDb | Pipeline Mode (PowerShell)
# Selective execution for DE pipeline stages.
# Usage:
#   .\pipeline-mode.ps1 start           # Start pipeline stack (postgres + airflow + etl-runner)
#   .\pipeline-mode.ps1 stop            # Stop pipeline stack
#   .\pipeline-mode.ps1 resume          # Resume full dev stack (neo4j/rustfs/duckdb)
#   .\pipeline-mode.ps1 status          # Show current state
#   .\pipeline-mode.ps1 run bronze      # Run bronze ingestion only
#   .\pipeline-mode.ps1 run silver      # Run silver ETL only (requires bronze Parquet)
#   .\pipeline-mode.ps1 run gold        # Run gold dbt + export only (requires silver tables)
#   .\pipeline-mode.ps1 run full        # Run full end-to-end pipeline
#   .\pipeline-mode.ps1 clean           # Drop silver/gold schemas, clean Parquet, restart

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "resume", "status", "run", "clean")]
    [string]$Action = "status",

    [Parameter(Position=1)]
    [string]$Stage = ""
)

$COMPOSE_FILE = "docker/docker-compose.yml"
$AIRFLOW = "docker exec elyssa-airflow"
$PG = "docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse"
$BRONZE_PATH = "/opt/airflow/output/bronze/"
$GOLD_PATH = "/opt/airflow/output/gold/"

# Load secrets from docker/.env (C1-C7) so no plaintext credentials live here.
function Get-EnvValue($key) {
    $envFile = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        Write-Warn "docker/.env not found — copy docker/.env.example to docker/.env first"
        return ""
    }
    $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
    if ($line) { return ($line -replace "^$key=", "").Trim() }
    return ""
}
$PG_PASSWORD = Get-EnvValue "GOLD_EXPORT_PG_PASSWORD"

function Write-Step($msg) {
    Write-Host ">>> $msg" -ForegroundColor Cyan
}

function Write-OK($msg) {
    Write-Host "[OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Wait-Healthy($container) {
    $attempts = 0
    while ($attempts -lt 60) {
        $status = docker inspect --format '{{json .State.Health.Status}}' $container 2>$null
        if ($status -eq '"healthy"') { return }
        Start-Sleep -Seconds 5
        $attempts++
    }
    Write-Warn "$container health check timed out"
}

function Invoke-Bronze {
    Write-Step "Spawning bronze ingestion (subprocess)..."
    & $AIRFLOW airflow dags trigger -r bronze_manual_$(Get-Date -Format 'yyyyMMddHHmmss') imdb_pipeline
    Write-OK "Bronze DAG triggered. Monitor: docker exec elyssa-airflow tail -f /tmp/bronze_runner.log"
}

function Invoke-Silver {
    Write-Step "Running silver ETL inside etl-runner..."
    docker exec elyssa-etl-runner python /opt/etl/data-engineering/orchestration/operators/silver_operator.py
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Silver ETL complete"
    } else {
        Write-Warn "Silver ETL failed (exit code: $LASTEXITCODE)"
    }
}

function Invoke-Gold {
    Write-Step "Running gold dbt build..."
    & $AIRFLOW dbt run --project-dir /opt/airflow/data-engineering/gold --profiles-dir /opt/airflow/data-engineering/gold --target prod --full-refresh
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Gold dbt run complete"
        Write-Step "Running gold dbt test..."
        & $AIRFLOW dbt test --project-dir /opt/airflow/data-engineering/gold --profiles-dir /opt/airflow/data-engineering/gold --target prod
        Write-Step "Running gold export..."
        if ([string]::IsNullOrEmpty($PG_PASSWORD)) {
            Write-Warn "GOLD_EXPORT_PG_PASSWORD missing from docker/.env — cannot run gold export"
            return
        }
        $env:PGPASSWORD = $PG_PASSWORD
        docker exec elyssa-airflow python -c "
import os; os.environ['GOLD_EXPORT_PG_PASSWORD'] = '$PG_PASSWORD'
from operators.gold_export_operator import GoldExportOperator
GoldExportOperator(task_id='gold_export').execute({})
"
        Write-OK "Gold export complete"
    } else {
        Write-Warn "Gold dbt run failed"
    }
}

function Clear-SilverGold {
    Write-Step "Dropping silver and gold schemas (all data)..."
    & $PG -c "DROP SCHEMA IF EXISTS silver CASCADE"
    & $PG -c "DROP SCHEMA IF EXISTS gold CASCADE"
    & $PG -c "CREATE SCHEMA silver"
    & $PG -c "CREATE SCHEMA gold"
    Write-OK "Schemas reset"
}

switch ($Action) {
    "start" {
        Write-Step "Stopping non-essential services..."
        docker compose -f $COMPOSE_FILE stop neo4j rustfs duckdb 2>$null
        Write-Step "Starting pipeline services..."
        docker compose -f $COMPOSE_FILE up -d postgres etl-runner airflow
        Wait-Healthy "elyssa-postgres"
        Wait-Healthy "elyssa-airflow"
        docker compose -f $COMPOSE_FILE ps
        Write-OK "Pipeline stack ready. Check: http://localhost:18081"
    }
    "stop" {
        Write-Step "Stopping pipeline stack..."
        docker compose -f $COMPOSE_FILE down
        Write-OK "Pipeline stopped"
    }
    "resume" {
        Write-Step "Starting full dev stack..."
        docker compose -f $COMPOSE_FILE up -d
        Start-Sleep -Seconds 10
        docker compose -f $COMPOSE_FILE ps
        Write-Warn "Full stack running (~8 GB+ allocation)"
    }
    "status" {
        Write-Host "=== Elyssa Pipeline Status ===" -ForegroundColor Cyan
        docker compose -f $COMPOSE_FILE ps 2>$null
        Write-Host "`nVmmemWSL:" -ForegroundColor Cyan
        Get-Process VmmemWSL -ErrorAction SilentlyContinue | Select-Object @{Name='MB';Expression={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table
        Write-Host "DAG runs:" -ForegroundColor Cyan
        & $PG -c "SELECT run_id, state, start_date FROM dag_run WHERE dag_id='imdb_pipeline' ORDER BY start_date DESC LIMIT 5" 2>$null
    }
    "run") {
        switch ($Stage) {
            "bronze" { Invoke-Bronze }
            "silver" { Invoke-Silver }
            "gold" { Invoke-Gold }
            "full" {
                Invoke-Bronze
                Write-Step "Waiting 5s for bronze subprocess..."
                Start-Sleep -Seconds 5
                # Wait for bronze .completed marker (up to 1 hour)
                $waited = 0
                while ($waited -lt 3600) {
                    $done = docker exec elyssa-airflow sh -c "test -f $BRONZE_PATH.completed && echo yes || echo no" 2>$null
                    if ($done -eq "yes") { Write-OK "Bronze completed"; break }
                    Start-Sleep -Seconds 30
                    $waited += 30
                }
                Invoke-Silver
                Invoke-Gold
            }
            default {
                Write-Warn "Unknown stage '$Stage'. Use: bronze, silver, gold, full"
            }
        }
    }
    "clean") {
        Write-Step "Cleaning pipeline state..."
        Clear-SilverGold
        docker run --rm -v elyssa_airflow_data:/data alpine sh -c "rm -rf /data/output/bronze/*.parquet /data/output/gold/* /data/output/tmp/* 2>/dev/null; echo done"
        Write-Step "Restarting pipeline stack..."
        docker compose -f $COMPOSE_FILE down
        docker compose -f $COMPOSE_FILE up -d postgres etl-runner airflow
        Wait-Healthy "elyssa-postgres"
        Wait-Healthy "elyssa-airflow"
        Write-OK "Clean start ready. Run: .\pipeline-mode.ps1 run full"
    }
}
