-- Consolidated Bear / Base / Bull monthly output -- one row per scenario x month, joining
-- fct_arr_forecast (company total), fct_pnl_reforecast, fct_headcount_forecast (summed across
-- function) and fct_cash_runway. This is the single table reports/forecast_runway_validation_
-- report.md's scenario section (and any future Power BI page) reads for Bear/Base/Bull.
-- No incremental GTM hiring in any of these three paths -- see fct_hiring_scenario for that
-- management-action dimension, layered onto Base only.
with headcount_total as (
    select path, month_end_date, sum(ending_headcount) as ending_headcount, bool_and(is_actual) as is_actual
    from fct_headcount_forecast
    where path in ('Bear', 'Base', 'Bull')
    group by 1, 2
),

arr as (
    select path, month_end_date, beginning_arr, new_logo_arr, expansion_arr, reactivation_arr,
           contraction_arr, churn_arr, ending_arr, is_actual, period_label
    from fct_arr_forecast
    where segment = 'Total' and path in ('Bear', 'Base', 'Bull')
),

pnl as (
    select path, month_end_date, total_revenue, subscription_revenue, services_revenue,
           gross_profit, total_opex, operating_income
    from fct_pnl_reforecast
    where path in ('Bear', 'Base', 'Bull')
),

cash as (
    select path, month_end_date, ending_cash, monthly_burn
    from fct_cash_runway
    where path in ('Bear', 'Base', 'Bull')
)

select
    a.path as scenario, a.month_end_date,
    a.beginning_arr, a.new_logo_arr, a.expansion_arr, a.reactivation_arr, a.contraction_arr,
    a.churn_arr, a.ending_arr,
    p.subscription_revenue, p.services_revenue, p.total_revenue, p.gross_profit,
    p.total_opex, p.operating_income,
    h.ending_headcount,
    c.ending_cash, c.monthly_burn,
    a.is_actual, a.period_label
from arr a
join pnl p on p.path = a.path and p.month_end_date = a.month_end_date
join headcount_total h on h.path = a.path and h.month_end_date = a.month_end_date
left join cash c on c.path = a.path and c.month_end_date = a.month_end_date
order by a.path, a.month_end_date
