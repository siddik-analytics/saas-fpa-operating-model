-- Monthly P&L, path x month. Actuals (dim_date.is_actual) are read unchanged from
-- fact_gl_actuals and replicated identically across every path. Forecast months (Jul-2026
-- onward) are built BOTTOM-UP and separately for COGS and each OpEx category, per
-- PHASE1_SPEC-analogous sections 21-23:
--
--   Subscription Revenue   reuses the SAME weighted-lag-of-ARR convention the actual ledger was
--                          generated with (config gl.subscription_revenue_lag_weights: 55% of
--                          month-1 ARR, 45% of month-2 ARR, /12) applied to fct_arr_forecast's
--                          own Total ARR path, so revenue does not jump discontinuously at the
--                          Jun/Jul cutover. NOT Ending ARR / 12 (PHASE1_SPEC-analogous section 19).
--   Services Revenue       trailing-12-month actual Services Revenue / New Logo ARR ratio,
--                          applied to forecast New Logo ARR that month (implementation-fee
--                          attach behaviour, config gl.services.implementation_fee_attach)
--   Subscription / Services COGS, S&M, R&D, G&A
--                          payroll component (headcount x loaded cost per FTE, by function,
--                          mapped to P&L category exactly as chart_of_accounts.yml's
--                          cost_centers block defines, including the Customer Success 60/40
--                          split) PLUS a non-payroll component held at the trailing-quarter
--                          (Apr-Jun 2026) actual run rate, flat and scenario-invariant
--   Sales Commissions      the one non-payroll exception: commission_expensed_share (0.41) x
--                          (New Logo ARR x 9% + Expansion ARR x 6%) -- responds to forecasted
--                          bookings, unlike every other non-payroll line. Commission
--                          Amortisation (account 6040) stays in the flat trailing-run-rate
--                          bucket -- it amortises PRE-forecast-period capitalised cost, and
--                          modelling its forward rollforward is ASC 340-40 territory (Phase 8,
--                          out of scope here; docs/forecast_runway.md).
--
-- gross margin (int_forecast_drivers, driver_category = 'margin') is NOT used as a P&L build
-- input here -- it is reported for validation only, alongside the margin this bottom-up build
-- actually produces.
with paths as (
    select 'Bear' as path union all select 'Base' union all select 'Bull'
    union all select 'Base_Targeted' union all select 'Base_FullClose'
),

month_seq as (
    select month_end_date, row_number() over (order by month_end_date) as rn from dim_date
),

arr_total as (
    select path, month_end_date, ending_arr, new_logo_arr, expansion_arr
    from fct_arr_forecast
    where segment = 'Total'
),

revenue_base as (
    select
        f.path, f.month_end_date, l1.ending_arr as arr_lag1, l2.ending_arr as arr_lag2
    from arr_total f
    join month_seq ms on ms.month_end_date = f.month_end_date
    join month_seq ms1 on ms1.rn = ms.rn - 1
    join arr_total l1 on l1.path = f.path and l1.month_end_date = ms1.month_end_date
    join month_seq ms2 on ms2.rn = ms.rn - 2
    join arr_total l2 on l2.path = f.path and l2.month_end_date = ms2.month_end_date
    where f.month_end_date >= date '2026-07-31'
),

services_ratio as (
    select
        sum(case when account_category = 'Services Revenue' then -actual_amount else 0 end)
        / nullif((select sum(new_logo_arr) from fct_arr_waterfall
                  where segment = 'Total' and month_end_date between date '2025-07-31' and date '2026-06-30'), 0)
        as ratio
    from stg_fact_gl_actuals
    where month_end_date between date '2025-07-31' and date '2026-06-30'
),

function_category_share as (
    -- chart_of_accounts.yml cost_centers block, rolled up to the eight PHASE1_SPEC-analogous
    -- reporting functions. Customer Success is the one split cost pool (CC-1200).
    select 'Sales' as function, 'Sales & Marketing' as category, 1.00 as share
    union all select 'Marketing', 'Sales & Marketing', 1.00
    union all select 'Customer Success', 'Subscription COGS', 0.60
    union all select 'Customer Success', 'Sales & Marketing', 0.40
    union all select 'Support & Cloud Ops', 'Subscription COGS', 1.00
    union all select 'Professional Services', 'Services COGS', 1.00
    union all select 'Engineering', 'Research & Development', 1.00
    union all select 'Product & Design', 'Research & Development', 1.00
    union all select 'G&A', 'General & Administrative', 1.00
),

payroll_cost_per_fte as (
    select segment as function, value from int_forecast_drivers
    where driver_category = 'opex' and driver_name = 'payroll_cost_per_fte_monthly'
),

payroll_forecast as (
    select
        hf.path, hf.month_end_date, fcs.category,
        sum(hf.ending_headcount * pcf.value * fcs.share) as payroll_cost
    from fct_headcount_forecast hf
    join function_category_share fcs on fcs.function = hf.function
    join payroll_cost_per_fte pcf on pcf.function = hf.function
    where hf.is_actual = false
    group by 1, 2, 3
),

payroll_pivot as (
    select path, month_end_date,
        sum(case when category = 'Subscription COGS' then payroll_cost else 0 end) as subscription_cogs_payroll,
        sum(case when category = 'Services COGS' then payroll_cost else 0 end) as services_cogs_payroll,
        sum(case when category = 'Sales & Marketing' then payroll_cost else 0 end) as sm_payroll,
        sum(case when category = 'Research & Development' then payroll_cost else 0 end) as rd_payroll,
        sum(case when category = 'General & Administrative' then payroll_cost else 0 end) as ga_payroll
    from payroll_forecast
    group by 1, 2
),

non_payroll_flat as (
    -- Trailing-quarter actual, ex-payroll accounts (6000/6010/6020) and ex-Sales Commissions
    -- (6030, bookings-driven instead) -- flat forward, scenario-invariant.
    select account_category,
           sum(actual_amount) / 3.0 as monthly_amount
    from stg_fact_gl_actuals
    where month_end_date between date '2026-04-30' and date '2026-06-30'
      and account_code not in (6000, 6010, 6020, 6030)
      and account_category not in ('Subscription Revenue', 'Services Revenue')
    group by 1
),

non_payroll_pivot as (
    select
        max(case when account_category = 'Subscription COGS' then monthly_amount else 0 end) as subscription_cogs_nonpayroll,
        max(case when account_category = 'Services COGS' then monthly_amount else 0 end) as services_cogs_nonpayroll,
        max(case when account_category = 'Sales & Marketing' then monthly_amount else 0 end) as sm_nonpayroll,
        max(case when account_category = 'Research & Development' then monthly_amount else 0 end) as rd_nonpayroll,
        max(case when account_category = 'General & Administrative' then monthly_amount else 0 end) as ga_nonpayroll
    from non_payroll_flat
),

commission_expense as (
    -- config: gl.commission_expensed_share (0.41), sales_reps.commission_rate_new (0.09),
    -- commission_rate_expansion (0.06) -- binding, hardcoded here the same way ramp_pct and
    -- quota are hardcoded elsewhere in this project against a binding config value.
    select path, month_end_date,
           0.41 * (new_logo_arr * 0.09 + greatest(expansion_arr, 0) * 0.06) as commission_cost
    from arr_total
    where month_end_date >= date '2026-07-31'
),

forecast_pnl as (
    select
        rb.path, rb.month_end_date,
        (0.55 * rb.arr_lag1 + 0.45 * rb.arr_lag2) / 12.0 as subscription_revenue,
        sr.ratio * af.new_logo_arr as services_revenue,
        coalesce(pp.subscription_cogs_payroll, 0) + npp.subscription_cogs_nonpayroll as subscription_cogs,
        coalesce(pp.services_cogs_payroll, 0) + npp.services_cogs_nonpayroll as services_cogs,
        coalesce(pp.sm_payroll, 0) + npp.sm_nonpayroll + coalesce(ce.commission_cost, 0) as sales_marketing,
        coalesce(pp.rd_payroll, 0) + npp.rd_nonpayroll as research_development,
        coalesce(pp.ga_payroll, 0) + npp.ga_nonpayroll as general_administrative,
        false as is_actual
    from revenue_base rb
    join arr_total af on af.path = rb.path and af.month_end_date = rb.month_end_date
    cross join services_ratio sr
    cross join non_payroll_pivot npp
    left join payroll_pivot pp on pp.path = rb.path and pp.month_end_date = rb.month_end_date
    left join commission_expense ce on ce.path = rb.path and ce.month_end_date = rb.month_end_date
),

actual_pnl_base as (
    select
        month_end_date,
        sum(case when account_category = 'Subscription Revenue' then -actual_amount else 0 end) as subscription_revenue,
        sum(case when account_category = 'Services Revenue' then -actual_amount else 0 end) as services_revenue,
        sum(case when account_category = 'Subscription COGS' then actual_amount else 0 end) as subscription_cogs,
        sum(case when account_category = 'Services COGS' then actual_amount else 0 end) as services_cogs,
        sum(case when account_category = 'Sales & Marketing' then actual_amount else 0 end) as sales_marketing,
        sum(case when account_category = 'Research & Development' then actual_amount else 0 end) as research_development,
        sum(case when account_category = 'General & Administrative' then actual_amount else 0 end) as general_administrative
    from stg_fact_gl_actuals
    where month_end_date in (select month_end_date from dim_date where is_actual)
    group by 1
),

actual_pnl as (
    select p.path, a.*, true as is_actual
    from actual_pnl_base a
    cross join paths p
),

combined as (
    select * from actual_pnl
    union all
    select * from forecast_pnl
)

select
    path, month_end_date,
    subscription_revenue, services_revenue,
    subscription_revenue + services_revenue as total_revenue,
    subscription_cogs, services_cogs,
    subscription_cogs + services_cogs as total_cogs,
    (subscription_revenue + services_revenue) - (subscription_cogs + services_cogs) as gross_profit,
    sales_marketing, research_development, general_administrative,
    sales_marketing + research_development + general_administrative as total_opex,
    ((subscription_revenue + services_revenue) - (subscription_cogs + services_cogs))
        - (sales_marketing + research_development + general_administrative) as operating_income,
    is_actual,
    case
        when is_actual then 'Actual'
        when month_end_date <= date '2026-12-31' then 'FY2026 Reforecast'
        else 'Forward Runway Projection'
    end as period_label
from combined
order by path, month_end_date
