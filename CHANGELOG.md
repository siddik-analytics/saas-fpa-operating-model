# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v0.1] — Synthetic data foundation with renewal mechanics

Phase 2 of the build described in `docs/PHASE1_SPEC.md`. Produces the raw source dataset that
every later phase reads, plus the machinery that proves it is coherent. No analytical layer,
no metrics, no forecast.

### Added

**Configuration**
- `config/assumptions.yml` holding every calibrated financial driver — anchors, segment
  definitions, contract mechanics, retention hazards, expansion behaviour, CRM targets, quotas
  and ramp, headcount and attrition, ledger cost drivers, and the two planning versions.
  Nothing a reviewer would want to challenge is buried in Python.
- `config/chart_of_accounts.yml` — 26 natural accounts crossed with 21 operating cost centres,
  each rolling up to one of the eight reporting functions and one of the seven approved P&L
  categories. Ten statistical accounts for the planning tables.
- `config/name_lists.yml` — curated components producing contractor-style customer names, with
  a banned-token list enforced by the validation suite.

**Generation**
- Deterministic seeded generator producing 13 source tables in `data/raw/`. Random streams are
  keyed per entity, so a customer's journey does not shift when other cohorts change size.
- Contract engine with monthly, annual and multi-year terms; churn and contraction confined to
  the anniversary or end of term; bounded early termination; mid-term co-termed expansion; and
  a 3–5% renewal price uplift expressed as a narrowing of the discount to list.
- Seats modelled as a penetration of the customer's own workforce, with a per-customer ceiling
  that expansion cannot exceed.
- Journey archetypes driving coherent multi-year customer histories, with churn hazard varying
  by segment, size, tenure and calendar year.
- Renewal seasonality emerging from acquisition seasonality rather than being imposed, giving
  Q1 and Q4 renewal concentration and lumpy monthly churn.
- CRM opportunities carrying the five reconciling differences the Phase 5 walk needs:
  signing-to-provisioning lag, TCV against ACV, wins that never provision, post-close
  amendments, and renewal uplift booked as an opportunity.
- Sales reps, employees and requisitions, with reps appearing in both `dim_sales_rep` and
  `dim_employee` so headcount and rep counts cannot drift apart, and requisition backfills tied
  to the terminations that caused them.
- General ledger built from drivers — payroll person by person, hosting per seat, commissions
  from closed-won ACV — never by spreading annual totals across months.
- FY2026 board budget and FY2026 Q2 reforecast, each built by applying movement components to
  the opening ARR the data actually carried rather than by typing an exit position.

**Calibration**
- Deterministic feedback loop solving nine parameter groups against the approved ARR, logo,
  new-logo ACV, retention and P&L anchors by staged bisection. No anchor value is written into
  the output.

**Validation and tests**
- `src/validate_sources.py` — 105 checks run against the committed CSVs rather than the
  generator in memory.
- `src/report.py` — generates `reports/source_validation_report.md` on every build.
- `tests/test_source_data.py` — 41 pytest tests covering reproducibility, the ARR and MRR
  identity, churn timing, segmentation, referential integrity and the anchors.
- `python -m src.build` runs the whole sequence and exits non-zero on a critical failure.

**Documentation**
- `README.md`, `docs/data_dictionary.md`, `docs/generation_methodology.md`.

### Notes

- `docs/PHASE1_SPEC.md` is frozen and unchanged.
- Nine documented departures from the specification are recorded in
  `docs/generation_methodology.md` section 8, covering the source-table count, the scope of
  `dim_customer`, the opening balance month, the `recent_new_logo` archetype, segment logo
  tolerance, the 198 FTE against 206 headcount reconciliation, row-count estimates, implied R&D
  compensation, and the treatment of the Enterprise NRR figure.
