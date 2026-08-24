-- Staging: typed pass-through of fact_forecast. No business logic.
--
-- Loaded ONLY as a benchmark for the Phase 6 independent driver-based forecast
-- (docs/forecast_runway.md). No model in 06_forecast joins to or reads from this table or
-- anything built on it; the comparison happens exclusively in the forecast validation report,
-- after fct_scenario_monthly is already fully computed. Natural ledger signs preserved, same
-- convention as stg_fact_gl_actuals / stg_fact_budget.
select
    version,
    cast(month_end_date as date) as month_end_date,
    cost_center,
    department,
    account_code,
    account_name,
    account_category,
    cast(forecast_amount as decimal(18, 2)) as forecast_amount
from raw_fact_forecast
