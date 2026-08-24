-- New Logo operating diagnosis -- WHY Base New Logo ARR is below Budget, separate from the
-- dollar bridge (fct_arr_budget_bridge). The Phase 6 forecast computes
-- New Logo ARR = LEAST(New Logo productive capacity, pipeline-supported bookings)
-- (int_gtm_capacity_pipeline_forecast, docs/forecast_runway.md section 4) -- a LEAST()
-- interaction, so "capacity variance" and "pipeline variance" cannot both be added into the same
-- dollar bridge without double-counting or under-counting whichever side does not bind in a given
-- segment-month. This table is therefore an EXPLANATORY diagnostic, grain segment x H2 2026,
-- never a second financial bridge: it reports which constraint actually bound, in how many of
-- the 6 H2 segment-months, and what each side of the LEAST() was worth, so a reader can see WHY
-- the bridge's New Logo ARR variance came out the size it did without implying two additive
-- causes.
with h2_months as (
    select month_end_date from dim_date
    where month_end_date between date '2026-07-31' and date '2026-12-31'
),

segment_detail as (
    select
        segment,
        count(*) as h2_segment_months,
        sum(case when binding_constraint = 'Pipeline' then 1 else 0 end) as h2_pipeline_bound_months,
        sum(case when binding_constraint = 'Capacity' then 1 else 0 end) as h2_capacity_bound_months,
        sum(pipeline_supported_bookings) as h2_pipeline_supported_arr,
        sum(new_logo_capacity) as h2_capacity_supported_arr,
        sum(constrained_new_logo_arr) as h2_constrained_new_logo_arr
    from int_gtm_capacity_pipeline_forecast
    where path = 'Base' and month_end_date in (select month_end_date from h2_months)
    group by 1
),

segment_binding as (
    select segment,
           case when h2_pipeline_bound_months > h2_capacity_bound_months then 'Pipeline'
                when h2_capacity_bound_months > h2_pipeline_bound_months then 'Capacity'
                else 'Mixed' end as primary_binding_constraint
    from segment_detail
),

total_detail as (
    select
        'Total' as segment,
        sum(h2_segment_months) as h2_segment_months,
        sum(h2_pipeline_bound_months) as h2_pipeline_bound_months,
        sum(h2_capacity_bound_months) as h2_capacity_bound_months,
        sum(h2_pipeline_supported_arr) as h2_pipeline_supported_arr,
        sum(h2_capacity_supported_arr) as h2_capacity_supported_arr,
        sum(h2_constrained_new_logo_arr) as h2_constrained_new_logo_arr
    from segment_detail
),

total_binding as (
    select 'Total' as segment,
           case when h2_pipeline_bound_months > h2_capacity_bound_months then 'Pipeline'
                when h2_capacity_bound_months > h2_pipeline_bound_months then 'Capacity'
                else 'Mixed' end as primary_binding_constraint
    from total_detail
),

detail_all as (
    select * from segment_detail
    union all
    select * from total_detail
),

binding_all as (
    select * from segment_binding
    union all
    select * from total_binding
),

fy26_new_logo as (
    select segment, budget_amount as budget_new_logo_arr, base_amount as base_new_logo_arr
    from int_budget_reforecast_comparison
    where metric_group = 'arr' and metric = 'new_logo_arr'
)

select
    d.segment,
    n.budget_new_logo_arr,
    n.base_new_logo_arr,
    n.base_new_logo_arr - n.budget_new_logo_arr as new_logo_arr_variance,
    d.h2_segment_months,
    d.h2_pipeline_bound_months,
    d.h2_capacity_bound_months,
    d.h2_pipeline_supported_arr,
    d.h2_capacity_supported_arr,
    d.h2_constrained_new_logo_arr,
    b.primary_binding_constraint
from detail_all d
join binding_all b using (segment)
join fy26_new_logo n using (segment)
order by case d.segment when 'Total' then 0 when 'SMB' then 1 when 'Mid-Market' then 2 when 'Enterprise' then 3 end
