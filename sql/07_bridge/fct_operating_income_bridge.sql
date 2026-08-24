-- FY2026 Operating Income / Loss: Board Budget -> Independent Base Reforecast. The one table
-- built for a CFO to read end to end: every revenue, COGS and OpEx variance signed by its actual
-- effect on profit (a revenue shortfall is negative; a cost UNDER-run is positive), so the chain
-- always reconciles to the exact Budget-to-Base operating-income difference.
with metrics as (
    select metric_group, metric, budget_amount, base_amount
    from int_budget_reforecast_comparison
    where (metric_group = 'revenue' and metric in ('subscription_revenue', 'services_revenue'))
       or (metric_group = 'cogs' and metric in ('subscription_cogs', 'services_cogs'))
       or (metric_group = 'opex' and metric in ('sales_marketing', 'research_development', 'general_administrative'))
),

anchors as (
    select
        sum(case when metric_group = 'revenue' then budget_amount
                 when metric_group = 'cogs' then -budget_amount
                 when metric_group = 'opex' then -budget_amount end) as budget_oi,
        sum(case when metric_group = 'revenue' then base_amount
                 when metric_group = 'cogs' then -base_amount
                 when metric_group = 'opex' then -base_amount end) as base_oi
    from metrics
),

lines as (
    select 1 as line_order, 'Budget Operating Income / (Loss)' as line_item, a.budget_oi as amount
    from anchors a
    union all
    select 2, 'Revenue variance - Subscription', base_amount - budget_amount
    from metrics where metric = 'subscription_revenue'
    union all
    select 3, 'Revenue variance - Services', base_amount - budget_amount
    from metrics where metric = 'services_revenue'
    union all
    select 4, 'Subscription COGS impact', -(base_amount - budget_amount)
    from metrics where metric = 'subscription_cogs'
    union all
    select 5, 'Services COGS impact', -(base_amount - budget_amount)
    from metrics where metric = 'services_cogs'
    union all
    select 6, 'Sales & Marketing OpEx impact', -(base_amount - budget_amount)
    from metrics where metric = 'sales_marketing'
    union all
    select 7, 'Research & Development OpEx impact', -(base_amount - budget_amount)
    from metrics where metric = 'research_development'
    union all
    select 8, 'General & Administrative OpEx impact', -(base_amount - budget_amount)
    from metrics where metric = 'general_administrative'
),

chain as (
    select *,
        sum(amount) over (order by line_order rows between unbounded preceding and current row) as running_balance
    from lines
),

anchor_end as (
    select 9 as line_order, 'Base Operating Income / (Loss)' as line_item, base_oi as amount, base_oi as running_balance
    from anchors
),

residual as (
    select max(c.running_balance) - max(a.amount) as residual
    from chain c cross join anchor_end a
    where c.line_order = 8
)

select line_order, line_item, amount, running_balance, (select residual from residual) as residual from chain
union all
select line_order, line_item, amount, running_balance, (select residual from residual) as residual from anchor_end
order by line_order
