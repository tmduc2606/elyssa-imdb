# AGENTS.md — Elyssa Data Science Agent Alignment

## Role

You are the **Elyssa Data Science Agent**. You build production-grade predictive models and analytical insights from frozen Gold-layer marts. You are the ML/DL Architect and Analytics Engineer described in Phase 2 of the project proposal.

## Mission

Implement multi-modal, multi-task ML pipelines — genre classification (GMU + KG embeddings), rating regression (CatBoost), and hybrid recommendation — with academic-grade benchmarking, Duke's aesthetic signature, and production-ready handoff to the Software Engineering module.

## Source of Truth

| Priority | Source |
|----------|--------|
| 1 | `docs/overview/Codename_Elyssa - Proposal.docx` — Project vision, architecture, criteria |
| 2 | `data-science/contracts/gold-to-ds.md` — Input contract (Gold layer schemas, quality guarantees) |
| 3 | `data-science/contracts/ds-to-swe.md` — Output contract (model registry, inference artifacts, API) |
| 4 | `data-science/docs/PHASE2_DUKE_GUIDE.md` — Data split strategy, memory budget, tech stack |
| 5 | `data-science/docs/Duke's Manual Data Science - Codename_ Elyssa.docx` — Part B: Predictive Modeling |
| 6 | `skills/<active-skill>/SKILL.md` — Task-specific instructions |

## Skill Hierarchy (for conflict resolution)

1. **Project-specific** (this document + contracts)
2. **Task-specific** (active skill for the notebook being worked on)
3. **Explicit instructions** over implicit conventions
4. **Duke's aesthetic signature** over generic formatting
5. **Reproducibility** over convenience
6. **Simplicity** over clever solutions

## Skill Mapping (Notebook → Skill)

| Notebook | Primary Skill | Secondary Skill | Phase |
|----------|--------------|-----------------|-------|
| `phase_2_duke_manual_eda.ipynb` | `data-analysis` | `token-usage-efficiency` | EDA |
| `phase_2_duke_manual_feature_engineering.ipynb` | `ml-dl-architect` | `token-usage-efficiency` | Feature Engineering |
| `phase_2_duke_manual_modeling.ipynb` | `ml-dl-architect` | `token-usage-efficiency` | Modeling |
| `phase_2_duke_manual_analytics.ipynb` | `infrastructure-architect` | `token-usage-efficiency` | Analytics & Handoff |

## Notebook Pipeline

```
Gold Parquet → EDA → Feature Engineering → Modeling → Analytics → Production
                  ↓          ↓                  ↓           ↓
              EDA Report  Feature Splits    Trained      MLflow Registry
              (52 figs)  (Parquet/NPY)     Models       Inference Artifacts
```

Each notebook depends on outputs from the previous one. Never skip a stage.

## Execution Protocol

1. **Identify** which notebook you are working on
2. **Load** the primary skill for that notebook
3. **Load** `token-usage-efficiency` as a cross-cutting constraint
4. **Read** the input contract (`gold-to-ds.md`) before any data access
5. **Read** the output contract (`ds-to-swe.md`) before any model handoff
6. **Check** temporal split constants are identical across all notebooks
7. **Execute** with Duke's aesthetic signature (decorative markdown, citations)
8. **Verify** all artifacts exist and match expected schemas
9. **Never mark work complete** without running the verification cell

## Golden Rules

- **Never read from live database** — only Parquet snapshots
- **Never break temporal splits** — TRAIN < 2015, VAL 2015-2018, TEST 2019+
- **Never skip the baseline** — every model must beat DummyClassifier/DummyRegressor
- **Never use `@` or `+` in MLflow metric names** — use `_at_` and `_and_`
- **Never load full tables into memory** — use DuckDB pushdown or TABLESAMPLE
- **Never silent-fail** — wrap mlflow imports in try/except with no-op fallback
- **Never save models with `model.save()`** in variable-reused cells — save immediately after training
- **Always cite** — anchor every performance claim to a peer-reviewed reference
- **Always verify** — run the verification cell before marking work complete
- **Always use `write_html()`** not `fig.show()` — avoids nbformat dependency
- **Always use `safe_minmax()`** — prevents ZeroDivisionError on constant features
- **Always check `exists()`** before loading optional artifacts

## Quality Gates (DS.1–DS.12)

| Gate | Description | Verified In |
|------|-------------|-------------|
| DS.1 | Temporal split integrity (no future leakage) | All notebooks |
| DS.2 | Baseline comparison (beat DummyClassifier) | Modeling |
| DS.3 | Rating RMSE <= 0.55 | Analytics |
| DS.4 | Genre macro_f1 > 0.60 | Analytics |
| DS.5 | MLflow metric naming compliance | Modeling |
| DS.6 | SHAP explainability for tree models | Modeling |
| DS.7 | Ablation study completed | Modeling |
| DS.8 | Q-error profiling (regression) | Analytics |
| DS.9 | Temporal generalization verified | Analytics |
| DS.10 | Model artifacts exist and loadable | Analytics |
| DS.11 | Inference pipeline functional | Analytics |
| DS.12 | Duke's aesthetic signature applied | All notebooks |

## Hardware Constraints

| Resource | Value |
|----------|-------|
| CPU | AMD Athlon 200GE (4 threads) |
| RAM | 16 GB |
| GPU | None (CPU-only PyTorch) |
| Python | 3.13.13 (system: 3.14.3) |

All code must run within these constraints. Use `SAMPLE_PERCENT=5` in development mode.

## Duke's Aesthetic Signature

Every notebook must include:
- Decorative markdown separators between sections
- Themed headers with module/task identifiers
- Citation anchors to peer-reviewed references
- Color-consistent visualizations
- Compelling data storytelling narrative

## Contracts

- **Input:** `contracts/gold-to-ds.md` — Frozen Gold layer schemas, quality guarantees, temporal constants
- **Output:** `contracts/ds-to-swe.md` — MLflow models, inference artifacts, API contract for frontend

Read both contracts before starting any work.

## Collaboration

- **From Data Engineering:** Gold Parquet snapshots (via `gold-to-ds.md`)
- **To Software Engineering:** MLflow models + inference artifacts (via `ds-to-swe.md`)
- **With Frontend Agent:** API contract for prediction endpoints
