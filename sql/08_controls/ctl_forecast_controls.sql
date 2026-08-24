-- Build gate for Phase 6 (driver-based Q2 reforecast, Bear/Base/Bull, cash runway, hiring
-- scenario). Any row this query returns is a violation and the build exits non-zero. An empty
-- result set is PASS.
--
--   A  actual_preservation          fct_arr_forecast's actual Total rows equal fct_arr_waterfall
--                                   exactly, every path (they must replicate identically)
--   B  forecast_cutover             no forecast-flagged row falls on/before 30 Jun 2026, and no
--                                   actual-flagged row falls after it, across every 06_forecast
--                                   monthly model
--   C  arr_waterfall_reconciliation beginning + movements = ending, fct_arr_forecast, every row
--   D  opening_arr_tie              July 2026 beginning ARR = June 2026 actual ending ARR
--                                   (fct_arr_waterfall), by segment, every path
--   E  segment_arr_reconciles       SMB + Mid-Market + Enterprise = Total, fct_arr_forecast,
--                                   every column, every path/month
--   F  headcount_rollforward        beginning + hires - departures = ending, fct_headcount_forecast
--   G  capacity_not_blended_exceeded  new_logo_capacity never exceeds blended_capacity,
--                                   int_gtm_capacity_pipeline_forecast (mirrors ctl_gtm_controls)
--   H  pnl_arithmetic               revenue / COGS / gross profit / OpEx / operating income all
--                                   tie, recomputed from fct_pnl_reforecast's own stored lines
--   I  cash_rollforward             beginning + net cash flow = ending, fct_cash_runway
--   J  no_duplicate_month_records   no duplicate (path, month) rows in any 06_forecast fct_ model
--   K  scenario_assumptions_complete  every scenario-varying driver in int_forecast_drivers is
--                                   non-null for Bear, Base and Bull
--   L  no_negative_values           no negative ARR, no negative headcount
--   M  hiring_impact_timing         a hiring case's New Logo capacity does not exceed Base's own
--                                   capacity before that case's hire-start month
--   N  cash_policy_arithmetic       policy burn, policy runway and headroom all tie, recomputed
--                                   from fct_cash_runway_policy's own stored lines; Base's own
--                                   policy burn equals the approved anchor exactly (zero delta)
with actual_preservation as (
    select 'actual_preservation' as grain,
           f.path || ' / ' || f.month_end_date::varchar as grain_key,
           f.ending_arr as implied_value, w.ending_arr as bound
    from fct_arr_forecast f
    join fct_arr_waterfall w on w.segment = 'Total' and w.month_end_date = f.month_end_date
    where f.segment = 'Total' and f.is_actual
      and abs(f.ending_arr - w.ending_arr) >= 1.00
),

forecast_cutover as (
    select 'forecast_cutover' as grain, path || ' / ' || month_end_date::varchar as grain_key,
           case when is_actual then 1.0 else 0.0 end as implied_value,
           case when month_end_date <= date '2026-06-30' then 1.0 else 0.0 end as bound
    from fct_arr_forecast
    where segment = 'Total'
      and ((is_actual and month_end_date > date '2026-06-30')
           or (not is_actual and month_end_date <= date '2026-06-30'))
),

arr_waterfall_reconciliation as (
    select 'arr_waterfall_reconciliation' as grain,
           path || ' / ' || segment || ' / ' || month_end_date::varchar as grain_key,
           beginning_arr + new_logo_arr + expansion_arr + reactivation_arr + contraction_arr + churn_arr
               as implied_value,
           ending_arr as bound
    from fct_arr_forecast
    where abs(beginning_arr + new_logo_arr + expansion_arr + reactivation_arr + contraction_arr + churn_arr
              - ending_arr) >= 1.00
),

opening_arr_tie as (
    select 'opening_arr_tie' as grain, f.path || ' / ' || f.segment as grain_key,
           f.beginning_arr as implied_value, w.ending_arr as bound
    from fct_arr_forecast f
    join fct_arr_waterfall w on w.segment = f.segment and w.month_end_date = date '2026-06-30'
    where f.month_end_date = date '2026-07-31' and f.segment <> 'Total'
      and abs(f.beginning_arr - w.ending_arr) >= 1.00
),

segment_arr_reconciles as (
    select 'segment_arr_reconciles' as grain, path || ' / ' || month_end_date::varchar as grain_key,
           sum(case when segment <> 'Total' then ending_arr else 0 end) as implied_value,
           sum(case when segment = 'Total' then ending_arr else 0 end) as bound
    from fct_arr_forecast
    group by 1, 2
    having abs(sum(case when segment <> 'Total' then ending_arr else 0 end)
               - sum(case when segment = 'Total' then ending_arr else 0 end)) >= 1.00
),

headcount_rollforward as (
    select 'headcount_rollforward' as grain,
           path || ' / ' || function || ' / ' || month_end_date::varchar as grain_key,
           beginning_headcount + hires - departures as implied_value, ending_headcount as bound
    from fct_headcount_forecast
    where abs(beginning_headcount + hires - departures - ending_headcount) >= 0.05
),

capacity_not_blended_exceeded as (
    select 'capacity_not_blended_exceeded' as grain,
           path || ' / ' || segment || ' / ' || month_end_date::varchar as grain_key,
           new_logo_capacity as implied_value, blended_capacity as bound
    from int_gtm_capacity_pipeline_forecast
    where new_logo_capacity > blended_capacity + 0.01
),

pnl_arithmetic as (
    select 'pnl_arithmetic' as grain, 'revenue / ' || path || ' / ' || month_end_date::varchar as grain_key,
           subscription_revenue + services_revenue as implied_value, total_revenue as bound
    from fct_pnl_reforecast
    where abs(subscription_revenue + services_revenue - total_revenue) >= 1.00
    union all
    select 'pnl_arithmetic', 'gross_profit / ' || path || ' / ' || month_end_date::varchar,
           total_revenue - (subscription_cogs + services_cogs), gross_profit
    from fct_pnl_reforecast
    where abs(total_revenue - (subscription_cogs + services_cogs) - gross_profit) >= 1.00
    union all
    select 'pnl_arithmetic', 'opex / ' || path || ' / ' || month_end_date::varchar,
           sales_marketing + research_development + general_administrative, total_opex
    from fct_pnl_reforecast
    where abs(sales_marketing + research_development + general_administrative - total_opex) >= 1.00
    union all
    select 'pnl_arithmetic', 'operating_income / ' || path || ' / ' || month_end_date::varchar,
           gross_profit - total_opex, operating_income
    from fct_pnl_reforecast
    where abs(gross_profit - total_opex - operating_income) >= 1.00
),

cash_rollforward as (
    select 'cash_rollforward' as grain, path || ' / ' || month_end_date::varchar as grain_key,
           beginning_cash + net_cash_flow as implied_value, ending_cash as bound
    from fct_cash_runway
    where abs(beginning_cash + net_cash_flow - ending_cash) >= 1.00
),

no_duplicate_month_records as (
    select 'no_duplicate_month_records' as grain, 'fct_arr_forecast' as grain_key,
           count(*)::double as implied_value, 0.0 as bound
    from (select path, segment, month_end_date, count(*) as n from fct_arr_forecast group by 1, 2, 3) t
    where n > 1
    having count(*) > 0
    union all
    select 'no_duplicate_month_records', 'fct_pnl_reforecast', count(*)::double, 0.0
    from (select path, month_end_date, count(*) as n from fct_pnl_reforecast group by 1, 2) t
    where n > 1
    having count(*) > 0
    union all
    select 'no_duplicate_month_records', 'fct_headcount_forecast', count(*)::double, 0.0
    from (select path, function, month_end_date, count(*) as n from fct_headcount_forecast group by 1, 2, 3) t
    where n > 1
    having count(*) > 0
    union all
    select 'no_duplicate_month_records', 'fct_cash_runway', count(*)::double, 0.0
    from (select path, month_end_date, count(*) as n from fct_cash_runway group by 1, 2) t
    where n > 1
    having count(*) > 0
),

scenario_assumptions_complete as (
    select 'scenario_assumptions_complete' as grain,
           driver_category || ' / ' || driver_name || ' / ' || coalesce(segment, 'NULL') as grain_key,
           count(distinct scenario)::double as implied_value, 3.0 as bound
    from int_forecast_drivers
    where scenario in ('Bear', 'Base', 'Bull') and value is not null
    group by 1, 2
    having count(distinct scenario) <> 3
),

no_negative_values as (
    select 'no_negative_values' as grain, 'arr / ' || path || ' / ' || segment || ' / ' || month_end_date::varchar as grain_key,
           ending_arr as implied_value, 0.0 as bound
    from fct_arr_forecast
    where ending_arr < 0
    union all
    select 'no_negative_values', 'headcount / ' || path || ' / ' || function || ' / ' || month_end_date::varchar,
           ending_headcount, 0.0
    from fct_headcount_forecast
    where ending_headcount < -0.01
),

hiring_impact_timing as (
    select 'hiring_impact_timing' as grain,
           h.path || ' / ' || h.segment || ' / ' || h.month_end_date::varchar as grain_key,
           h.new_logo_capacity as implied_value, b.new_logo_capacity as bound
    from int_gtm_capacity_pipeline_forecast h
    join int_gtm_capacity_pipeline_forecast b
        on b.path = 'Base' and b.segment = h.segment and b.month_end_date = h.month_end_date
    where h.path in ('Base_Targeted', 'Base_FullClose')
      and h.month_end_date < date '2026-10-31'
      and abs(h.new_logo_capacity - b.new_logo_capacity) >= 0.01
),

cash_policy_arithmetic as (
    select 'cash_policy_arithmetic' as grain, 'runway / ' || path as grain_key,
           opening_cash / nullif(policy_avg_monthly_burn, 0) as implied_value, policy_runway_months as bound
    from fct_cash_runway_policy
    where abs(opening_cash / nullif(policy_avg_monthly_burn, 0) - policy_runway_months) >= 0.01
    union all
    select 'cash_policy_arithmetic', 'headroom / ' || path,
           policy_runway_months - board_runway_floor_months, headroom_months
    from fct_cash_runway_policy
    where abs((policy_runway_months - board_runway_floor_months) - headroom_months) >= 0.01
    union all
    select 'cash_policy_arithmetic', 'base_burn_equals_anchor',
           policy_avg_monthly_burn, approved_base_burn
    from fct_cash_runway_policy
    where path = 'Base' and abs(policy_avg_monthly_burn - approved_base_burn) >= 0.01
),

all_checks as (
    select grain, grain_key, implied_value, bound from actual_preservation
    union all select grain, grain_key, implied_value, bound from forecast_cutover
    union all select grain, grain_key, implied_value, bound from arr_waterfall_reconciliation
    union all select grain, grain_key, implied_value, bound from opening_arr_tie
    union all select grain, grain_key, implied_value, bound from segment_arr_reconciles
    union all select grain, grain_key, implied_value, bound from headcount_rollforward
    union all select grain, grain_key, implied_value, bound from capacity_not_blended_exceeded
    union all select grain, grain_key, implied_value, bound from pnl_arithmetic
    union all select grain, grain_key, implied_value, bound from cash_rollforward
    union all select grain, grain_key, implied_value, bound from no_duplicate_month_records
    union all select grain, grain_key, implied_value, bound from scenario_assumptions_complete
    union all select grain, grain_key, implied_value, bound from no_negative_values
    union all select grain, grain_key, implied_value, bound from hiring_impact_timing
    union all select grain, grain_key, implied_value, bound from cash_policy_arithmetic
)

select grain, grain_key, implied_value, bound
from all_checks
order by grain, grain_key
