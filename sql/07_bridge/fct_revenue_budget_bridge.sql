-- FY2026 Revenue: Board Budget -> Independent Base Reforecast, split Subscription / Services /
-- Total. Grain: revenue_line x line_order.
--
-- Subscription Revenue is decomposed using the SAME weighted-lag-of-ARR mechanic
-- fct_pnl_reforecast already uses (config gl.subscription_revenue_lag_weights: 55% of month-1
-- ARR + 45% of month-2 ARR, /12; docs/forecast_runway.md section 6), run over BOTH the Budget's
-- own monthly ARR path (fact_budget account 9000) and the Base ARR path
-- (fct_arr_forecast), so the ARR effect is apples-to-apples under one recognition mechanic:
--
--   Budget Subscription Revenue (stated)
--   + Recognition-mechanic effect     the SAME lag formula applied to Budget's own ARR path,
--                                      minus Budget's stated figure -- how much of Budget's own
--                                      number diverges from a pure ARR-lag mechanic
--   + ARR / recurring-base effect     the lag formula applied to the Base ARR path minus the
--                                      same formula applied to the Budget ARR path -- the pure
--                                      effect of a lower/higher ARR base, recognition mechanic held constant
--   + H1 actual-vs-mechanical residual   Jan-Jun 2026 is REALISED actual revenue for Base
--                                      (fct_pnl_reforecast reads it straight from the GL, not the
--                                      lag formula), so this line reconciles the mechanical
--                                      full-year estimate to the actual-plus-forecast figure
--   = Base Subscription Revenue (actual)
--
-- Services Revenue uses the analogous mechanic: trailing-12-month actual Services-Revenue-to-
-- New-Logo-ARR ratio (config gl.services.implementation_fee_attach; docs/forecast_runway.md
-- section 6), applied to Budget's and Base's own FY2026 New Logo ARR.
--
-- No "Other" catch-all; every line is a calculated effect, never a plug (PHASE1_SPEC-analogous
-- governing constraint: derive, never fabricate).
with fy26_months as (
    select month_end_date from dim_date where month_end_date between date '2026-01-31' and date '2026-12-31'
),

month_seq as (
    select month_end_date, row_number() over (order by month_end_date) as rn from dim_date
),

-- ============================================================================
-- Subscription Revenue
-- ============================================================================
budget_arr_series as (
    select month_end_date, ending_arr as arr from fct_arr_waterfall
    where segment = 'Total' and month_end_date <= date '2025-12-31'
    union all
    select month_end_date, budget_amount as arr from stg_fact_budget
    where account_code = 9000 and month_end_date in (select month_end_date from fy26_months)
),

base_arr_series as (
    select month_end_date, ending_arr as arr from fct_arr_forecast
    where path = 'Base' and segment = 'Total'
),

lagged as (
    select f.month_end_date,
           bl1.arr as budget_lag1, bl2.arr as budget_lag2,
           al1.arr as base_lag1, al2.arr as base_lag2
    from fy26_months f
    join month_seq ms on ms.month_end_date = f.month_end_date
    join month_seq ms1 on ms1.rn = ms.rn - 1
    join month_seq ms2 on ms2.rn = ms.rn - 2
    join budget_arr_series bl1 on bl1.month_end_date = ms1.month_end_date
    join budget_arr_series bl2 on bl2.month_end_date = ms2.month_end_date
    join base_arr_series al1 on al1.month_end_date = ms1.month_end_date
    join base_arr_series al2 on al2.month_end_date = ms2.month_end_date
),

sub_rev_mechanical as (
    select
        sum((0.55 * budget_lag1 + 0.45 * budget_lag2) / 12.0) as budget_implied,
        sum((0.55 * base_lag1 + 0.45 * base_lag2) / 12.0) as base_implied
    from lagged
),

sub_rev_real as (
    select
        max(case when metric = 'subscription_revenue' then budget_amount end) as budget_stated,
        max(case when metric = 'subscription_revenue' then base_amount end) as base_real
    from int_budget_reforecast_comparison
    where metric_group = 'revenue'
),

sub_rev_lines as (
    select 'Subscription Revenue' as revenue_line, 1 as line_order, 'Budget Subscription Revenue' as line_item,
           r.budget_stated as amount
    from sub_rev_real r
    union all
    select 'Subscription Revenue', 2, 'Recognition-mechanic effect (lag formula vs. Budget stated)',
           m.budget_implied - r.budget_stated
    from sub_rev_mechanical m cross join sub_rev_real r
    union all
    select 'Subscription Revenue', 3, 'ARR / recurring-base effect',
           m.base_implied - m.budget_implied
    from sub_rev_mechanical m
    union all
    select 'Subscription Revenue', 4, 'H1 actual-vs-mechanical residual',
           r.base_real - m.base_implied
    from sub_rev_mechanical m cross join sub_rev_real r
    union all
    select 'Subscription Revenue', 5, 'Base Subscription Revenue', r.base_real
    from sub_rev_real r
),

-- ============================================================================
-- Services Revenue
-- ============================================================================
services_ratio as (
    select
        sum(case when account_category = 'Services Revenue' then -actual_amount else 0 end)
        / nullif((select sum(new_logo_arr) from fct_arr_waterfall
                  where segment = 'Total' and month_end_date between date '2025-07-31' and date '2026-06-30'), 0)
        as ratio
    from stg_fact_gl_actuals
    where month_end_date between date '2025-07-31' and date '2026-06-30'
),

new_logo_fy as (
    select
        max(case when metric = 'new_logo_arr' then budget_amount end) as budget_nl,
        max(case when metric = 'new_logo_arr' then base_amount end) as base_nl
    from int_budget_reforecast_comparison
    where metric_group = 'arr' and segment = 'Total'
),

svc_rev_real as (
    select
        max(case when metric = 'services_revenue' then budget_amount end) as budget_stated,
        max(case when metric = 'services_revenue' then base_amount end) as base_real
    from int_budget_reforecast_comparison
    where metric_group = 'revenue'
),

svc_rev_mechanical as (
    select sr.ratio * nl.budget_nl as budget_implied, sr.ratio * nl.base_nl as base_implied
    from services_ratio sr cross join new_logo_fy nl
),

svc_rev_lines as (
    select 'Services Revenue' as revenue_line, 1 as line_order, 'Budget Services Revenue' as line_item,
           r.budget_stated as amount
    from svc_rev_real r
    union all
    select 'Services Revenue', 2, 'Attach-rate mechanic effect (ratio formula vs. Budget stated)',
           m.budget_implied - r.budget_stated
    from svc_rev_mechanical m cross join svc_rev_real r
    union all
    select 'Services Revenue', 3, 'New Logo ARR effect',
           m.base_implied - m.budget_implied
    from svc_rev_mechanical m
    union all
    select 'Services Revenue', 4, 'H1 actual-vs-mechanical residual',
           r.base_real - m.base_implied
    from svc_rev_mechanical m cross join svc_rev_real r
    union all
    select 'Services Revenue', 5, 'Base Services Revenue', r.base_real
    from svc_rev_real r
),

all_lines as (
    select * from sub_rev_lines
    union all
    select * from svc_rev_lines
),

total_lines as (
    select 'Total Revenue' as revenue_line, line_order,
           case line_order
               when 1 then 'Budget Total Revenue'
               when 2 then 'Recognition-mechanic + attach-rate effect (combined)'
               when 3 then 'ARR / New Logo effect (combined)'
               when 4 then 'H1 actual-vs-mechanical residual (combined)'
               when 5 then 'Base Total Revenue' end as line_item,
           sum(amount) as amount
    from all_lines
    group by 1, 2
),

combined as (
    select * from all_lines
    union all
    select * from total_lines
),

-- Lines 1-4 are an additive delta chain; line 5 (the Base anchor) is a total, not a further
-- delta, and is therefore never added into the running balance -- the same convention
-- fct_arr_budget_bridge uses for its own start/end anchor rows.
chain as (
    select *,
        sum(amount) over (partition by revenue_line order by line_order rows between unbounded preceding and current row)
            as running_balance
    from combined
    where line_order <= 4
),

anchor as (
    select revenue_line, line_order, line_item, amount, amount as running_balance
    from combined
    where line_order = 5
),

with_running as (
    select * from chain
    union all
    select * from anchor
),

residuals as (
    select c.revenue_line, max(c.running_balance) - max(a.amount) as residual
    from chain c
    join anchor a using (revenue_line)
    where c.line_order = 4
    group by 1
)

select w.revenue_line, w.line_order, w.line_item, w.amount, w.running_balance, r.residual
from with_running w
join residuals r using (revenue_line)
order by
    case revenue_line when 'Subscription Revenue' then 1 when 'Services Revenue' then 2 when 'Total Revenue' then 3 end,
    line_order
