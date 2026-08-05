# Changelog

All notable milestones of the Elyssa-IMDb platform. Data Science module history lives in
[`data-science/CHANGELOG.md`](data-science/CHANGELOG.md).

## 2026-08-05 — Pre-Release Revision (v1.0.0-rc.1 → v1.0.0-rc.2)

- CI/CD all green: 8 workflows (CI, api-gateway, ci-de, ci-ds, ds-tests, ci-web, cd, trivy-scan) on `main`
- Trivy image scans clean: Airflow image hardened — 35 HIGH/CRITICAL findings cleared (litellm, GitPython, aiohttp, pyasn1 upgrades; ray/unused tooling removed)
- CI runner disk-full fixes: `--no-cache-dir` on all pip installs, free-space before image builds, build-cache pruning
- Compose env alignment: `GRAFANA_PASSWORD` + `RUSTFS_SECRET_KEY` interpolation, `POSTGRES_PASSWORD` for build
- DS CI stabilised: Python 3.13-only matrix, deterministic fixtures (gold marts + DS artifacts) via `generate_ci_fixtures.py`
- Requirements sync for pre-release: web API `scikit-learn` aligned to 1.9.x (trained joblib compatibility), DS deps pinned to `.venv` (`pyarrow==24.0.0` added; polars/pycountry/psycopg2/ipykernel exact-pinned)
- Pre-release `v1.0.0-rc.2` published (full-stack: DE + DS + Web + MLOps)

## 2026-08-04 — Phase-2 Rehearsal Success

- DE pipeline: full 18/18 task success (7 h 22 m, 212 M → 355 M → 241 M rows)
- Freshness SLA root cause fix (`logical_date` NULL + fork caching)
- Performance metrics report + 12 pipeline figures generated

## 2026-08-03 — DS v3.1.0

- DS pipeline: interactions, leakage guard, SHAP optimization
- DE pipeline: Bronze/Silver successful run

## 2026-07-29 — Phase 1 Final Inspection

- DE Gold layer handoff complete: dbt star-schema, DQ checks, export to `marts/gold/`

## 2026-07-19 — DS v3.0.0

- Data Science: modular `src/`, 50+ tests, quality gates (RMSE ≤ 0.55, Macro F1 > 0.60)

## 2026-06-24 — Project Inception

- Elyssa-IMDb platform kickoff: proposal, architecture, module contracts
