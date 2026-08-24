-- FY2026 Gross Profit and Gross Margin: Board Budget -> Independent Base Reforecast.
-- Grain: line_order (dollar bridge, unit='usd') plus three margin rows (unit='pct'/'bps').
--
-- Base carries LOWER revenue but HIGHER gross profit than Budget -- the management insight
-- section 9 asks this bridge to explain, not merely report. Decomposed into revenue and COGS
-- impacts, with COGS split payroll vs. non-payroll (the same split
-- int_budget_reforecast_comparison already derives, reusing fct_pnl_reforecast's own
-- people-vs-non-people cost framework rather than a fresh cost analysis) so a reader can see
-- whether the margin improvement is a revenue-mix effect or a cost effect.
with revenue_totals as (
    select
        max(case when metric = 'total_revenue' then budget_amount end) as budget_revenue,
        max(case when metric = 'total_revenue' then base_amount end) as base_revenue
    from int_budget_reforecast_comparison
    where metric_group = 'revenue'
),

cogs_totals as (
    select
        max(case when metric = 'total_cogs' then budget_amount end) as budget_cogs,
        max(case when metric = 'total_cogs' then base_amount end) as base_cogs
    from int_budget_reforecast_comparison
    where metric_group = 'cogs'
),

cogs_driver as (
    select
        max(case when metric = 'subscription_cogs_payroll' then budget_amount end) as budget_sub_payroll,
        max(case when metric = 'subscription_cogs_payroll' then base_amount end) as base_sub_payroll,
        max(case when metric = 'subscription_cogs_nonpayroll' then budget_amount end) as budget_sub_nonpayroll,
        max(case when metric = 'subscription_cogs_nonpayroll' then base_amount end) as base_sub_nonpayroll,
        max(case when metric = 'services_cogs_payroll' then budget_amount end) as budget_svc_payroll,
        max(case when metric = 'services_cogs_payroll' then base_amount end) as base_svc_payroll,
        max(case when metric = 'services_cogs_nonpayroll' then budget_amount end) as budget_svc_nonpayroll,
        max(case when metric = 'services_cogs_nonpayroll' then base_amount end) as base_svc_nonpayroll
    from int_budget_reforecast_comparison
    where metric_group = 'cogs_driver'
),

gp_anchors as (
    select
        r.budget_revenue - c.budget_cogs as budget_gp,
        r.base_revenue - c.base_cogs as base_gp
    from revenue_totals r cross join cogs_totals c
),

usd_lines as (
    select 1 as line_order, 'Budget Gross Profit' as line_item, 'usd' as unit, a.budget_gp as amount
    from gp_anchors a
    union all
    select 2, 'Revenue impact', 'usd', r.base_revenue - r.budget_revenue
    from revenue_totals r
    union all
    select 3, 'Subscription COGS - payroll impact', 'usd', -(d.base_sub_payroll - d.budget_sub_payroll)
    from cogs_driver d
    union all
    select 4, 'Subscription COGS - non-payroll impact', 'usd', -(d.base_sub_nonpayroll - d.budget_sub_nonpayroll)
    from cogs_driver d
    union all
    select 5, 'Services COGS - payroll impact', 'usd', -(d.base_svc_payroll - d.budget_svc_payroll)
    from cogs_driver d
    union all
    select 6, 'Services COGS - non-payroll impact', 'usd', -(d.base_svc_nonpayroll - d.budget_svc_nonpayroll)
    from cogs_driver d
),

chain as (
    select *,
        sum(amount) over (order by line_order rows between unbounded preceding and current row) as running_balance
    from usd_lines
),

anchor_end as (
    select 7 as line_order, 'Base Gross Profit' as line_item, 'usd' as unit, base_gp as amount, base_gp as running_balance
    from gp_anchors
),

residual as (
    select max(c.running_balance) - max(a.amount) as residual
    from chain c cross join anchor_end a
    where c.line_order = 6
),

margin_rows as (
    select 8 as line_order, 'Budget Gross Margin %' as line_item, 'pct' as unit,
           a.budget_gp / nullif(r.budget_revenue, 0) as amount, a.budget_gp / nullif(r.budget_revenue, 0) as running_balance
    from gp_anchors a cross join revenue_totals r
    union all
    select 9, 'Base Gross Margin %', 'pct',
           a.base_gp / nullif(r.base_revenue, 0), a.base_gp / nullif(r.base_revenue, 0)
    from gp_anchors a cross join revenue_totals r
    union all
    select 10, 'Gross Margin variance', 'bps',
           ((a.base_gp / nullif(r.base_revenue, 0)) - (a.budget_gp / nullif(r.budget_revenue, 0))) * 10000,
           ((a.base_gp / nullif(r.base_revenue, 0)) - (a.budget_gp / nullif(r.budget_revenue, 0))) * 10000
    from gp_anchors a cross join revenue_totals r
)

select line_order, line_item, unit, amount, running_balance,
       (select residual from residual) as residual
from chain
union all
select line_order, line_item, unit, amount, running_balance, (select residual from residual) as residual
from anchor_end
union all
select line_order, line_item, unit, amount, running_balance, (select residual from residual) as residual
from margin_rows
order by line_order
