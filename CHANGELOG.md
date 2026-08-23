# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v0.1] - Synthetic data foundation with renewal mechanics

### Added
- Config-first assumption set (`config/assumptions.yml`, `config/chart_of_accounts.yml`,
  `config/name_lists.yml`) holding every calibrated financial driver.
- Deterministic, seeded synthetic generator (`src/generate_data.py` and the `src/gen_*`
  modules) producing 13 raw source tables in `data/raw/`.
- Contract engine with monthly / annual / multi-year terms, anniversary-only churn and
  contraction for termed contracts, bounded early termination, mid-term co-termed
  expansion, and 3-5% renewal price uplift tracked separately from seat and module growth.
- Renewal seasonality producing Q1 and Q4 ATR concentration and lumpy monthly churn.
- Customer journey archetypes driving coherent multi-year customer histories.
- CRM opportunity generation with controlled, explainable reconciliation differences
  (signing-to-provisioning lag, TCV vs ACV, non-provisioned wins, post-close amendments).
- Sales rep, employee, requisition, GL actuals, board budget and Q2 reforecast sources.
- Source validation suite (`src/validate_sources.py`) and generated
  `reports/source_validation_report.md`.
- Build entry point `python -m src.build`, non-zero exit on critical validation failure.
- pytest suite covering determinism, ARR identity, churn timing, segmentation and anchors.

### Notes
- Phase 1 specification (`docs/PHASE1_SPEC.md`) is frozen and unchanged.
- Deviations from the specification's approximate row-count estimates are recorded in
  `docs/generation_methodology.md`.
