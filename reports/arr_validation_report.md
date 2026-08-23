# ARR validation report

Helio Systems, Inc. Phase 3, ARR engine and movement classification.

**PASS** - `ctl_arr_reconciliation` returned 0 violation row(s) across company-month, segment-month, full-period and product/customer-tie checks. Tolerance $1.00.

Every figure below is computed by querying the DuckDB analytical layer built by `python -m src.run_sql`, not typed in by hand. Rebuild with the same command; the report is regenerated on every build.

> **Grain.** Movement classification is customer-grain (`fct_arr_movement`), per PHASE1_SPEC 8.2. `fct_arr_product_movement` exists separately for product-mix questions and does not feed this waterfall — see docs/arr_engine.md.

## Monthly ARR trend

Company-level waterfall, every actual month (`fct_arr_waterfall`, `segment = 'Total'`).

| month_end_date | beginning_arr | new_logo_arr | expansion_arr | reactivation_arr | contraction_arr | churn_arr | ending_arr |
|---|---|---|---|---|---|---|---|
| 2024-01-31 | 18,571,137.00 | 525,566.76 | 219,226.44 | 0.00 | -258,461.88 | -149,570.16 | 18,907,898.16 |
| 2024-02-29 | 18,907,898.16 | 356,830.68 | 278,988.36 | 0.00 | -91,263.12 | -156,948.96 | 19,295,505.12 |
| 2024-03-31 | 19,295,505.12 | 831,032.04 | 312,089.64 | 0.00 | -65,536.80 | -323,996.88 | 20,049,093.12 |
| 2024-04-30 | 20,049,093.12 | 216,228.96 | 537,914.40 | 0.00 | -57,366.72 | -205,350.00 | 20,540,519.76 |
| 2024-05-31 | 20,540,519.76 | 383,789.52 | 243,323.76 | 8,655.48 | -45,964.32 | -166,052.52 | 20,964,271.68 |
| 2024-06-30 | 20,964,271.68 | 461,600.28 | 292,981.80 | 34,328.64 | -81,439.44 | -127,409.52 | 21,544,333.44 |
| 2024-07-31 | 21,544,333.44 | 320,339.76 | 316,543.44 | 33,770.28 | -88,843.92 | -120,242.64 | 22,005,900.36 |
| 2024-08-31 | 22,005,900.36 | 148,772.52 | 324,913.68 | 7,010.52 | -52,441.80 | -445,745.16 | 21,988,410.12 |
| 2024-09-30 | 21,988,410.12 | 301,297.92 | 188,901.84 | 18,563.64 | -40,384.08 | -53,116.92 | 22,403,672.52 |
| 2024-10-31 | 22,403,672.52 | 432,548.28 | 239,530.80 | 5,769.72 | -72,395.64 | -253,401.36 | 22,755,724.32 |
| 2024-11-30 | 22,755,724.32 | 418,852.68 | 400,393.20 | 0.00 | -136,010.52 | -132,382.68 | 23,306,577.00 |
| 2024-12-31 | 23,306,577.00 | 1,219,456.56 | 403,755.48 | 0.00 | -153,569.64 | -281,022.00 | 24,495,197.40 |
| 2025-01-31 | 24,495,197.40 | 763,989.24 | 208,523.88 | 5,379.00 | -356,906.40 | -433,404.48 | 24,682,778.64 |
| 2025-02-28 | 24,682,778.64 | 398,202.84 | 450,903.12 | 0.00 | -110,046.24 | -189,502.92 | 25,232,335.44 |
| 2025-03-31 | 25,232,335.44 | 482,289.00 | 339,030.96 | 7,012.20 | -120,597.12 | -125,741.04 | 25,814,329.44 |
| 2025-04-30 | 25,814,329.44 | 289,522.08 | 568,274.88 | 41,077.32 | -140,806.80 | -142,746.84 | 26,429,650.08 |
| 2025-05-31 | 26,429,650.08 | 266,066.16 | 214,662.36 | 12,462.48 | -91,199.88 | -240,511.20 | 26,591,130.00 |
| 2025-06-30 | 26,591,130.00 | 408,324.00 | 332,059.56 | 0.00 | -45,796.20 | -147,946.44 | 27,137,770.92 |
| 2025-07-31 | 27,137,770.92 | 148,504.68 | 364,045.92 | 2,735.28 | -97,174.92 | -88,185.00 | 27,467,696.88 |
| 2025-08-31 | 27,467,696.88 | 254,568.00 | 339,460.68 | 2,107.44 | -73,086.12 | -197,466.12 | 27,793,280.76 |
| 2025-09-30 | 27,793,280.76 | 265,998.84 | 295,512.48 | 0.00 | -46,792.80 | -189,627.96 | 28,118,371.32 |
| 2025-10-31 | 28,118,371.32 | 427,038.12 | 493,697.64 | 0.00 | -124,445.04 | -162,396.00 | 28,752,266.04 |
| 2025-11-30 | 28,752,266.04 | 771,199.20 | 366,765.00 | 0.00 | -173,070.72 | -328,723.80 | 29,388,435.72 |
| 2025-12-31 | 29,388,435.72 | 815,749.32 | 245,648.28 | 37,735.80 | -77,452.20 | -220,801.08 | 30,189,315.84 |
| 2026-01-31 | 30,189,315.84 | 267,424.44 | 361,621.20 | 3,132.00 | -451,736.88 | -188,907.24 | 30,180,849.36 |
| 2026-02-28 | 30,180,849.36 | 347,874.72 | 303,632.88 | 10,064.52 | -150,335.16 | -113,861.40 | 30,578,224.92 |
| 2026-03-31 | 30,578,224.92 | 452,642.28 | 237,688.44 | 7,982.76 | -205,926.12 | -233,182.92 | 30,837,429.36 |
| 2026-04-30 | 30,837,429.36 | 134,448.48 | 820,157.04 | 3,643.20 | -61,498.80 | -286,825.44 | 31,447,353.84 |
| 2026-05-31 | 31,447,353.84 | 170,863.20 | 1,119,731.40 | 14,374.56 | -139,362.12 | -119,750.52 | 32,493,210.36 |
| 2026-06-30 | 32,493,210.36 | 650,292.36 | 510,603.96 | 20,643.24 | -95,907.84 | -562,121.76 | 33,016,720.32 |

## FY2025 ARR waterfall

Company total, generated from `fct_arr_movement` against the PHASE1_SPEC 2.3 reconciling set (`config/assumptions.yml: anchors.fy2025_arr_waterfall`).

| Component | Target $ | Generated $ | Variance |
|---|---|---|---|
| Beginning ARR | 24,200,000 | 24,495,197.40 | +1.2% |
| New Logo ARR | 5,000,000 | 5,291,451.48 | +5.8% |
| Expansion ARR | 4,400,000 | 4,218,584.76 | -4.1% |
| Reactivation ARR | 200,000 | 108,509.52 | -45.7% |
| Contraction ARR | -900,000 | -1,457,374.44 | -61.9% |
| Churn ARR | -2,800,000 | -2,467,052.88 | +11.9% |
| Ending ARR | 30,100,000 | 30,189,315.84 | +0.3% |

Net new ARR (generated): $5,694,118. Reconciliation identity holds to the cent (see Reconciliation results below).

## Movement totals, FY2025

Customer-month record counts and dollar movement by classification (`fct_arr_movement`).

| movement_type | customer_months | total_movement_arr |
|---|---|---|
| Churn | 183 | -2,467,052.88 |
| Contraction | 186 | -1,457,374.44 |
| Expansion | 659 | 4,218,584.76 |
| New Logo | 232 | 5,291,451.48 |
| No Change | 12,208 | 0.00 |
| Reactivation | 10 | 108,509.52 |

## Movement by segment, FY2025

| segment | beginning_arr | new_logo_arr | expansion_arr | reactivation_arr | contraction_arr | churn_arr | ending_arr |
|---|---|---|---|---|---|---|---|
| Enterprise | 10,080,994.56 | 1,450,206.48 | 717,826.08 | 0.00 | -394,610.04 | -252,620.64 | 11,601,796.44 |
| Mid-Market | 10,460,274.72 | 2,227,544.16 | 2,974,842.96 | 71,517.96 | -889,872.96 | -1,037,939.52 | 13,806,367.32 |
| SMB | 3,953,928.12 | 1,613,700.84 | 525,915.72 | 36,991.56 | -172,891.44 | -1,176,492.72 | 4,781,152.08 |

## Reconciliation results

`ctl_arr_reconciliation` at every required grain. A PASS row means zero violations; the build gate fails if any grain returns a violation.

| Grain group | Violations | Result |
|---|---:|---|
| `ctl_arr_reconciliation` | 0 | PASS |
| `ctl_retention_bounds` | 0 | PASS |
| `ctl_gtm_controls` | 0 | PASS |

## Largest monthly churn periods

Company-level, all actual months, ranked by churn ARR magnitude.

| month_end_date | churn_dollars |
|---|---|
| 2026-06-30 | 562,121.76 |
| 2024-08-31 | 445,745.16 |
| 2025-01-31 | 433,404.48 |
| 2025-11-30 | 328,723.80 |
| 2024-03-31 | 323,996.88 |

## Largest monthly expansion periods

Company-level, all actual months, ranked by expansion ARR.

| month_end_date | expansion_arr |
|---|---|
| 2026-05-31 | 1,119,731.40 |
| 2026-04-30 | 820,157.04 |
| 2025-04-30 | 568,274.88 |
| 2024-04-30 | 537,914.40 |
| 2026-06-30 | 510,603.96 |

## Differences from Phase 1 anchors

ARR level at each anchor date, from `fct_arr_waterfall` (`segment = 'Total'`), against `config/assumptions.yml: anchors.arr` — the same targets Phase 2 validated the source data against.

| Date | Target ARR | Generated ARR | Variance |
|---|---|---|---|
| 2023-12-31 | 18,500,000 | 18,571,137.00 | +0.4% |
| 2024-12-31 | 24,200,000 | 24,495,197.40 | +1.2% |
| 2025-12-31 | 30,100,000 | 30,189,315.84 | +0.3% |
| 2026-06-30 | 32,800,000 | 33,016,720.32 | +0.7% |

**On the movement-category composition.** The FY2025 waterfall above ties almost exactly on beginning and ending ARR (both within the Phase 2 anchor tolerance), but the split between movement categories departs further from the PHASE1_SPEC target than the level does — most visibly, contraction runs higher and reactivation runs lower than the approved reconciling set. This is a source-generation effect, not a classification defect: the Phase 2 calibration loop (`docs/generation_methodology.md` section 5) solves nine parameter groups against total ARR, logo counts, new-logo ACV and logo retention by segment — it does not target the dollar split across new logo, expansion, reactivation, contraction and churn. `fct_arr_movement` correctly classifies whatever the generator produced; the generator was never calibrated to the waterfall's component composition, only to its endpoints. Reactivation event *counts* (21) match the Phase 2 source validation report's reactivation count exactly, and churn timing (min/median/max monthly churn dollars) closely tracks the Phase 2 source-level churn lumpiness check, which corroborates that the classification logic itself is sound.

