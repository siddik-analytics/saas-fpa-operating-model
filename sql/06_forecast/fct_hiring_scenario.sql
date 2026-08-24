-- The runway-constrained hiring decision. Three cases, all evaluated under BASE operating
-- conditions (PHASE1_SPEC-analogous section 18: hiring is a management action, kept separate
-- from Bear/Base/Bull operating performance):
--
--   No Incremental GTM Hiring        = the Base path itself, zero hires beyond already-open reqs
--   Targeted / Runway-Constrained    hires only where CAPACITY, not pipeline, binds (segment_gap,
--                                    int_gtm_capacity_pipeline_forecast)
--   Full Capacity-Close Hiring       hires the full computed capacity gap in every segment,
--                                    including a segment where pipeline is already the binding
--                                    constraint -- deliberately shown so the report can quantify
--                                    ARR bought that the funnel cannot actually convert
--
-- Every "incremental_*" column is this case's value MINUS the No-Incremental (Base) value for
-- the same month -- the cost AND the ramped capacity of a hire only ever show up from its own
-- hire month forward (PHASE1_SPEC-analogous section 33, control O).
with case_paths as (
    select 'No Incremental GTM Hiring' as case_label, 'Base' as path
    union all select 'Targeted / Runway-Constrained Hiring', 'Base_Targeted'
    union all select 'Full Capacity-Close Hiring', 'Base_FullClose'
),

-- incremental_hires in int_gtm_capacity_pipeline_forecast is a STOCK -- the total hire count for
-- that (path, segment), repeated on every month's row -- never a monthly flow, so it is read
-- directly here and never run through a cumulative window sum.
cumulative_hires as (
    select path, month_end_date,
           sum(incremental_hires) as cumulative_hires,
           sum(new_logo_capacity) as new_logo_capacity, sum(pipeline_supported_bookings) as pipeline_supported
    from int_gtm_capacity_pipeline_forecast
    where path in ('Base', 'Base_Targeted', 'Base_FullClose')
    group by 1, 2
),

arr as (
    select path, month_end_date, new_logo_arr, ending_arr
    from fct_arr_forecast
    where segment = 'Total' and path in ('Base', 'Base_Targeted', 'Base_FullClose')
),

pnl as (
    select path, month_end_date, total_revenue, operating_income
    from fct_pnl_reforecast
    where path in ('Base', 'Base_Targeted', 'Base_FullClose')
),

headcount as (
    select path, month_end_date, sum(ending_headcount) as ending_headcount
    from fct_headcount_forecast
    where path in ('Base', 'Base_Targeted', 'Base_FullClose') and is_actual = false
    group by 1, 2
),

cash as (
    select path, month_end_date, ending_cash from fct_cash_runway
    where path in ('Base', 'Base_Targeted', 'Base_FullClose')
),

joined as (
    select
        cp.case_label, cp.path, ch.month_end_date, ch.cumulative_hires,
        ch.new_logo_capacity, ch.pipeline_supported,
        a.new_logo_arr, a.ending_arr, p.total_revenue, p.operating_income,
        h.ending_headcount, c.ending_cash
    from case_paths cp
    join cumulative_hires ch on ch.path = cp.path
    join arr a on a.path = cp.path and a.month_end_date = ch.month_end_date
    join pnl p on p.path = cp.path and p.month_end_date = ch.month_end_date
    join headcount h on h.path = cp.path and h.month_end_date = ch.month_end_date
    left join cash c on c.path = cp.path and c.month_end_date = ch.month_end_date
),

base_values as (
    select month_end_date, ending_arr as base_ending_arr, total_revenue as base_total_revenue,
           operating_income as base_operating_income, ending_cash as base_ending_cash
    from joined
    where path = 'Base'
)

select
    j.case_label, j.path, j.month_end_date, j.cumulative_hires,
    j.new_logo_capacity, j.pipeline_supported, j.new_logo_arr, j.ending_arr,
    j.total_revenue, j.operating_income, j.ending_headcount, j.ending_cash,
    j.ending_arr - b.base_ending_arr as incremental_ending_arr,
    j.total_revenue - b.base_total_revenue as incremental_revenue,
    j.operating_income - b.base_operating_income as incremental_operating_income,
    j.ending_cash - b.base_ending_cash as incremental_cash_impact,
    case
        when j.month_end_date <= date '2026-12-31' then 'FY2026 Reforecast'
        else 'Forward Runway Projection'
    end as period_label
from joined j
join base_values b on b.month_end_date = j.month_end_date
order by j.case_label, j.month_end_date
