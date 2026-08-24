-- FY2026 OpEx: Board Budget -> Independent Base Reforecast, by category (Sales & Marketing,
-- R&D, G&A, Total OpEx). Grain: category x line_order.
--
-- Decomposed into payroll, sales commissions (Sales & Marketing only -- the one line
-- fct_pnl_reforecast computes from forecast bookings rather than a flat run rate) and
-- non-payroll run rate, reusing exactly the people-vs-non-people cost-driver split
-- int_budget_reforecast_comparison already derives (docs/forecast_runway.md section 6) rather
-- than rebuilding a parallel cost forecast. Every dollar of variance is assigned to one of these
-- three calculated drivers -- no "other" catch-all.
with category_meta as (
    select 'Sales & Marketing' as category, 'sales_marketing' as prefix, true as has_commission
    union all select 'Research & Development', 'research_development', false
    union all select 'General & Administrative', 'general_administrative', false
),

category_totals as (
    select metric as category_key,
           budget_amount as budget_total, base_amount as base_total
    from int_budget_reforecast_comparison
    where metric_group = 'opex' and metric in ('sales_marketing', 'research_development', 'general_administrative')
),

drivers as (
    select
        cm.category, cm.prefix, cm.has_commission,
        max(case when d.metric = cm.prefix || '_payroll' then d.budget_amount end) as budget_payroll,
        max(case when d.metric = cm.prefix || '_payroll' then d.base_amount end) as base_payroll,
        max(case when d.metric = cm.prefix || '_nonpayroll' then d.budget_amount end) as budget_nonpayroll,
        max(case when d.metric = cm.prefix || '_nonpayroll' then d.base_amount end) as base_nonpayroll,
        max(case when d.metric = 'sales_marketing_commission' then d.budget_amount end) as budget_commission,
        max(case when d.metric = 'sales_marketing_commission' then d.base_amount end) as base_commission
    from category_meta cm
    left join int_budget_reforecast_comparison d
        on d.metric_group = 'opex_driver'
       and d.metric in (cm.prefix || '_payroll', cm.prefix || '_nonpayroll',
                         case when cm.has_commission then 'sales_marketing_commission' end)
    group by 1, 2, 3
),

category_lines as (
    select d.category, 1 as line_order, 'Budget ' || d.category as line_item, t.budget_total as amount
    from drivers d join category_totals t on t.category_key = d.prefix
    union all
    select d.category, 2, 'Payroll impact', d.base_payroll - d.budget_payroll
    from drivers d
    union all
    select d.category, 3, 'Sales commissions impact',
           coalesce(d.base_commission, 0) - coalesce(d.budget_commission, 0)
    from drivers d
    where d.has_commission
    union all
    select d.category, 4, 'Non-payroll run-rate impact', d.base_nonpayroll - d.budget_nonpayroll
    from drivers d
),

chain as (
    select *,
        sum(amount) over (partition by category order by line_order rows between unbounded preceding and current row)
            as running_balance
    from category_lines
),

anchors as (
    select d.category, 5 as line_order, 'Base ' || d.category as line_item,
           t.base_total as amount, t.base_total as running_balance
    from drivers d join category_totals t on t.category_key = d.prefix
),

residuals as (
    select c.category, max(c.running_balance) - max(a.amount) as residual
    from chain c
    join anchors a on a.category = c.category
    where c.line_order = 4
    group by 1
),

category_rows as (
    select c.category, c.line_order, c.line_item, c.amount, c.running_balance, r.residual
    from chain c join residuals r using (category)
    union all
    select a.category, a.line_order, a.line_item, a.amount, a.running_balance, r.residual
    from anchors a join residuals r using (category)
),

-- ============================================================================
-- Total OpEx rollup
-- ============================================================================
total_rows as (
    select
        'Total OpEx' as category, line_order,
        case line_order
            when 1 then 'Budget Total OpEx'
            when 2 then 'Payroll impact (all categories)'
            when 3 then 'Sales commissions impact'
            when 4 then 'Non-payroll run-rate impact (all categories)'
            when 5 then 'Base Total OpEx' end as line_item,
        sum(amount) as amount
    from category_rows
    where line_order <> 3 or category = 'Sales & Marketing'
    group by 1, 2
),

total_chain as (
    select category, line_order, line_item, amount,
        sum(amount) over (order by line_order rows between unbounded preceding and current row) as running_balance
    from total_rows
    where line_order <= 4
),

total_anchor as (
    select category, line_order, line_item, amount, amount as running_balance
    from total_rows
    where line_order = 5
),

total_residual as (
    select max(c.running_balance) - max(a.amount) as residual
    from total_chain c cross join total_anchor a
    where c.line_order = 4
),

total_final as (
    select category, line_order, line_item, amount, running_balance, (select residual from total_residual) as residual
    from total_chain
    union all
    select category, line_order, line_item, amount, running_balance, (select residual from total_residual) as residual
    from total_anchor
),

all_final as (
    select category, line_order, line_item, amount, running_balance, residual from category_rows
    union all
    select category, line_order, line_item, amount, running_balance, residual from total_final
)

select category, line_order, line_item, amount, running_balance, residual
from all_final
order by
    case category when 'Sales & Marketing' then 1 when 'Research & Development' then 2
                   when 'General & Administrative' then 3 when 'Total OpEx' then 4 end,
    line_order
