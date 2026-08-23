-- Staging: typed pass-through of fact_budget. No business logic.
--
-- Loaded from Phase 5 for exactly one purpose: the FY2026-Board-Approved "New Logo ARR" memo
-- row (account 9010), read as the existing, already-approved New ARR target for capacity and
-- pipeline coverage (PHASE1_SPEC 8.9). This is a static planning input already produced by
-- Phase 2, not driver-based forecasting -- no forecast logic is built in this phase, and
-- fact_forecast (the Q2 reforecast) is not loaded here at all; that belongs to Phase 6.
select
    version,
    cast(month_end_date as date) as month_end_date,
    cost_center,
    department,
    account_code,
    account_name,
    account_category,
    cast(budget_amount as decimal(18, 2)) as budget_amount
from raw_fact_budget
