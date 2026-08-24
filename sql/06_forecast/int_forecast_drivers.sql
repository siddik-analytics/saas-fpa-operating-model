-- Phase 6 driver hub. Every Bear/Base/Bull-resolved value every other 06_forecast model reads
-- lives here -- long/tidy grain (driver_category, driver_name, scenario, segment). scenario =
-- 'All' where a driver is not scenario-varied; segment = 'All' where a driver is company- or
-- function-level rather than segment-level. This IS the compact, recruiter-inspectable
-- assumptions table PHASE1_SPEC-analogous section 38 asks for --
-- reports/forecast_runway_validation_report.md renders it directly.
--
-- Base-case values are DERIVED from a trailing 12-actual-month window (2025-07-31 to
-- 2026-06-30) of the approved Phase 3/4/5 marts -- "most likely operating outcome using current
-- evidence", per docs/forecast_runway.md. Bear/Base/Bull apply the management-assumption
-- multipliers in stg_forecast_assumptions (config/assumptions.yml: forecast.scenario_multipliers)
-- on top of that derived Base value. Nothing here reads fact_budget or fact_forecast.
with segments as (
    select 'SMB' as segment union all select 'Mid-Market' union all select 'Enterprise'
),

multipliers as (
    select driver as driver_name, scenario, value as multiplier
    from stg_forecast_assumptions
    where category = 'scenario_multiplier' and segment = 'All'
),

-- ============================================================================
-- New Logo: win rate (pipeline -> booked conversion), by segment
-- ============================================================================
win_rate_base as (
    select segment,
           sum(case when is_won then 1.0 else 0.0 end) / nullif(count(*), 0) as base_value
    from int_crm_opportunity_normalized
    where deal_type = 'New Logo' and (is_won or is_lost)
      and actual_close_date between date '2025-07-01' and date '2026-06-30'
    group by 1
),

win_rate as (
    select 'new_logo' as driver_category, 'win_rate' as driver_name, m.scenario, b.segment,
           least(1.0, b.base_value * m.multiplier) as value, 'rate' as unit, 'historical' as source_type,
           'Trailing-12-month New Logo win rate (int_crm_opportunity_normalized), x win_rate multiplier, capped at 100%' as basis
    from win_rate_base b
    cross join multipliers m
    where m.driver_name = 'win_rate'
),

attainment_multiplier as (
    select 'new_logo' as driver_category, 'attainment_multiplier' as driver_name, scenario, 'All' as segment,
           multiplier as value, 'multiplier' as unit, 'management_assumption' as source_type,
           'Applied directly to fct_sales_capacity.expected_attainment, already the Base-case trailing-realised figure' as basis
    from multipliers where driver_name = 'attainment'
),

-- ============================================================================
-- Pipeline: forward monthly New Logo pipeline creation, by segment
-- ============================================================================
pipeline_creation_actual as (
    select segment, sum(acv) / 12.0 as base_monthly_acv
    from int_crm_opportunity_normalized
    where deal_type = 'New Logo' and created_date between date '2025-07-01' and date '2026-06-30'
    group by 1
),

pipeline_creation as (
    select 'pipeline' as driver_category, 'creation_monthly_acv' as driver_name, m.scenario, b.segment,
           b.base_monthly_acv * m.multiplier as value, 'usd_per_month' as unit, 'historical' as source_type,
           'Trailing-12-month average monthly New Logo pipeline creation ACV (int_crm_opportunity_normalized), x pipeline_creation multiplier' as basis
    from pipeline_creation_actual b
    cross join multipliers m
    where m.driver_name = 'pipeline_creation'
),

pipeline_lag as (
    select 'pipeline' as driver_category, 'creation_to_close_lag_months' as driver_name,
           'All' as scenario, segment, value, unit, source_type, note as basis
    from stg_forecast_assumptions
    where category = 'pipeline' and driver = 'creation_to_close_lag_months'
),

-- ============================================================================
-- Expansion: monthly rate applied to each month's opening segment ARR
-- ============================================================================
expansion_actual as (
    select segment, month_end_date, expansion_arr, beginning_arr
    from fct_arr_waterfall
    where segment <> 'Total' and month_end_date between date '2025-07-31' and date '2026-06-30'
),

expansion_base as (
    select segment, sum(expansion_arr) / 12.0 / nullif(avg(beginning_arr), 0) as base_monthly_rate
    from expansion_actual
    group by 1
),

expansion as (
    select 'expansion' as driver_category, 'monthly_rate_of_beginning_arr' as driver_name, m.scenario, b.segment,
           b.base_monthly_rate * m.multiplier as value, 'rate' as unit, 'historical' as source_type,
           'Trailing-12-month expansion ARR / average beginning ARR (fct_arr_waterfall), x expansion multiplier' as basis
    from expansion_base b
    cross join multipliers m
    where m.driver_name = 'expansion'
),

-- ============================================================================
-- Retention: ATR-driven churn/contraction shares (fct_renewal_base x these
-- shares gives the renewal-timed component every forecast month) plus a flat
-- non-ATR (month-to-month / early-exit) monthly baseline
-- ============================================================================
renewal_outcomes_hist as (
    select segment, renewal_outcome, atr_arr, renewed_arr, outcome_month
    from fct_renewal_outcomes
    where outcome_month in (select month_end_date from dim_date where is_actual)
),

atr_shares as (
    select segment,
        sum(case when renewal_outcome in ('Churned', 'Early Termination') then atr_arr else 0 end)
            / nullif(sum(atr_arr), 0) as churn_share,
        sum(case when renewal_outcome = 'Renewed with Contraction' then atr_arr - renewed_arr else 0 end)
            / nullif(sum(atr_arr), 0) as contraction_share
    from renewal_outcomes_hist
    group by 1
),

trailing_actual_movement as (
    select segment, sum(-churn_arr) as churn_total, sum(-contraction_arr) as contraction_total
    from fct_arr_waterfall
    where segment <> 'Total' and month_end_date between date '2025-07-31' and date '2026-06-30'
    group by 1
),

trailing_atr_realized as (
    select segment,
        sum(case when renewal_outcome in ('Churned', 'Early Termination') then atr_arr else 0 end) as atr_churn_total,
        sum(case when renewal_outcome = 'Renewed with Contraction' then atr_arr - renewed_arr else 0 end) as atr_contraction_total
    from renewal_outcomes_hist
    where outcome_month between date '2025-07-31' and date '2026-06-30'
    group by 1
),

baseline_nonatr as (
    select t.segment,
        greatest(0, t.churn_total - coalesce(a.atr_churn_total, 0)) / 12.0 as baseline_churn_monthly,
        greatest(0, t.contraction_total - coalesce(a.atr_contraction_total, 0)) / 12.0 as baseline_contraction_monthly
    from trailing_actual_movement t
    left join trailing_atr_realized a on a.segment = t.segment
),

churn_share as (
    select 'retention' as driver_category, 'churn_share_of_atr' as driver_name, m.scenario, s.segment,
           least(1.0, s.churn_share * m.multiplier) as value, 'rate' as unit, 'historical' as source_type,
           'All-time realised Churned + Early Termination share of resolved-renewal ATR (fct_renewal_outcomes), x retention_severity multiplier, capped at 100%' as basis
    from atr_shares s
    cross join multipliers m
    where m.driver_name = 'retention_severity'
),

contraction_share as (
    select 'retention' as driver_category, 'contraction_share_of_atr' as driver_name, m.scenario, s.segment,
           least(1.0, s.contraction_share * m.multiplier) as value, 'rate' as unit, 'historical' as source_type,
           'All-time realised Renewed-with-Contraction ARR loss share of resolved-renewal ATR (fct_renewal_outcomes), x retention_severity multiplier, capped at 100%' as basis
    from atr_shares s
    cross join multipliers m
    where m.driver_name = 'retention_severity'
),

baseline_churn as (
    select 'retention' as driver_category, 'baseline_nonatr_churn_monthly' as driver_name, m.scenario, b.segment,
           b.baseline_churn_monthly * m.multiplier as value, 'usd_per_month' as unit, 'historical' as source_type,
           'Trailing-12-month actual churn ARR run rate net of the ATR-driven portion realised in the same window (fct_arr_waterfall, fct_renewal_outcomes), x retention_severity multiplier' as basis
    from baseline_nonatr b
    cross join multipliers m
    where m.driver_name = 'retention_severity'
),

baseline_contraction as (
    select 'retention' as driver_category, 'baseline_nonatr_contraction_monthly' as driver_name, m.scenario, b.segment,
           b.baseline_contraction_monthly * m.multiplier as value, 'usd_per_month' as unit, 'historical' as source_type,
           'Trailing-12-month actual contraction ARR run rate net of the ATR-driven portion realised in the same window (fct_arr_waterfall, fct_renewal_outcomes), x retention_severity multiplier' as basis
    from baseline_nonatr b
    cross join multipliers m
    where m.driver_name = 'retention_severity'
),

-- ============================================================================
-- Reactivation -- flat, scenario-invariant by design (config: forecast.reactivation_scenario_invariant)
-- ============================================================================
reactivation_base as (
    select segment, sum(reactivation_arr) / 12.0 as base_value
    from fct_arr_waterfall
    where segment <> 'Total' and month_end_date between date '2025-07-31' and date '2026-06-30'
    group by 1
),

reactivation as (
    select 'reactivation' as driver_category, 'monthly_arr' as driver_name, 'All' as scenario, segment,
           base_value as value, 'usd_per_month' as unit, 'historical' as source_type,
           'Trailing-12-month average monthly Reactivation ARR (fct_arr_waterfall); scenario-invariant by design' as basis
    from reactivation_base
),

-- ============================================================================
-- Gross margin -- company-level, subscription and services kept separate
-- ============================================================================
margin_inputs as (
    select
        sum(case when account_category = 'Subscription Revenue' then -actual_amount else 0 end) as sub_rev,
        sum(case when account_category = 'Services Revenue' then -actual_amount else 0 end) as svc_rev,
        sum(case when account_category = 'Subscription COGS' then actual_amount else 0 end) as sub_cogs,
        sum(case when account_category = 'Services COGS' then actual_amount else 0 end) as svc_cogs
    from stg_fact_gl_actuals
    where month_end_date between date '2025-07-31' and date '2026-06-30'
),

margins as (
    select 'margin' as driver_category, 'subscription_cogs_pct_of_revenue' as driver_name, 'All' as scenario, 'All' as segment,
           sub_cogs / nullif(sub_rev, 0) as value, 'rate' as unit, 'historical' as source_type,
           'Trailing 12 actual months, Subscription COGS / Subscription Revenue (fact_gl_actuals)' as basis
    from margin_inputs
    union all
    select 'margin', 'services_cogs_pct_of_revenue', 'All', 'All',
           svc_cogs / nullif(svc_rev, 0), 'rate', 'historical',
           'Trailing 12 actual months, Services COGS / Services Revenue (fact_gl_actuals)'
    from margin_inputs
),

-- ============================================================================
-- Payroll -- loaded monthly cost per FTE, by function
-- ============================================================================
cost_center_function_ranked as (
    select cost_center, function, count(*) as n,
           row_number() over (partition by cost_center order by count(*) desc) as rn
    from dim_employee
    group by 1, 2
),

cost_center_function as (
    select cost_center, function from cost_center_function_ranked where rn = 1
),

payroll_window_months as (
    select month_end_date from dim_date
    where is_actual and month_end_date between date '2026-01-31' and date '2026-06-30'
),

payroll_actual as (
    select ccf.function, g.month_end_date, sum(g.actual_amount) as payroll_cost
    from stg_fact_gl_actuals g
    join cost_center_function ccf on ccf.cost_center = g.cost_center
    where g.account_code in (6000, 6010, 6020)
      and g.month_end_date in (select month_end_date from payroll_window_months)
    group by 1, 2
),

headcount_actual as (
    select ccf.function, m.month_end_date, count(distinct e.employee_id) as headcount
    from dim_employee e
    join cost_center_function ccf on ccf.cost_center = e.cost_center
    cross join payroll_window_months m
    where e.hire_date <= m.month_end_date
      and (e.termination_date is null or e.termination_date > m.month_end_date)
    group by 1, 2
),

payroll_per_fte as (
    select p.function, avg(p.payroll_cost) / nullif(avg(h.headcount), 0) as base_value
    from payroll_actual p
    join headcount_actual h on h.function = p.function and h.month_end_date = p.month_end_date
    group by 1
),

payroll as (
    select 'opex' as driver_category, 'payroll_cost_per_fte_monthly' as driver_name, 'All' as scenario, function as segment,
           base_value as value, 'usd_per_month' as unit, 'historical' as source_type,
           'H1 2026 actual GL payroll (Salaries + Bonus + Payroll Taxes & Benefits) / average H1 2026 actual headcount, by function (fact_gl_actuals, dim_employee)' as basis
    from payroll_per_fte
),

combined as (
    select * from win_rate
    union all select * from attainment_multiplier
    union all select * from pipeline_creation
    union all select * from pipeline_lag
    union all select * from expansion
    union all select * from churn_share
    union all select * from contraction_share
    union all select * from baseline_churn
    union all select * from baseline_contraction
    union all select * from reactivation
    union all select * from margins
    union all select * from payroll
)

select driver_category, driver_name, scenario, segment, value, unit, source_type, basis
from combined
order by driver_category, driver_name, scenario, segment
