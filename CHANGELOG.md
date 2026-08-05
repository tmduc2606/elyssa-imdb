# Changelog

All notable milestones of the Elyssa-IMDb platform. Data Science module history lives in
[`data-science/CHANGELOG.md`](data-science/CHANGELOG.md).

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
