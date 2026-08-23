-- ARR waterfall, parameterised by segment and company grain. Aggregates fct_arr_movement;
-- classification itself stays customer-grain and happens upstream (PHASE1_SPEC 8.2).
--
-- Grain: month_end_date x segment, where segment is 'SMB' / 'Mid-Market' / 'Enterprise' for
-- the segment-level rows and 'Total' for the company-level rollup. contraction_arr and
-- churn_arr are signed negative, so the reconciliation identity is a plain sum:
--   beginning_arr + new_logo_arr + expansion_arr + reactivation_arr
--     + contraction_arr + churn_arr = ending_arr
with by_segment as (
    select
        month_end_date,
        segment,
        sum(beg_arr) as beginning_arr,
        sum(case when movement_type = 'New Logo'     then movement_arr else 0 end) as new_logo_arr,
        sum(case when movement_type = 'Expansion'    then movement_arr else 0 end) as expansion_arr,
        sum(case when movement_type = 'Reactivation' then movement_arr else 0 end) as reactivation_arr,
        sum(case when movement_type = 'Contraction'  then movement_arr else 0 end) as contraction_arr,
        sum(case when movement_type = 'Churn'        then movement_arr else 0 end) as churn_arr,
        sum(end_arr) as ending_arr
    from fct_arr_movement
    group by 1, 2
),

by_company as (
    select
        month_end_date,
        'Total' as segment,
        sum(beg_arr) as beginning_arr,
        sum(case when movement_type = 'New Logo'     then movement_arr else 0 end) as new_logo_arr,
        sum(case when movement_type = 'Expansion'    then movement_arr else 0 end) as expansion_arr,
        sum(case when movement_type = 'Reactivation' then movement_arr else 0 end) as reactivation_arr,
        sum(case when movement_type = 'Contraction'  then movement_arr else 0 end) as contraction_arr,
        sum(case when movement_type = 'Churn'        then movement_arr else 0 end) as churn_arr,
        sum(end_arr) as ending_arr
    from fct_arr_movement
    group by 1
),

combined as (
    select * from by_segment
    union all
    select * from by_company
)

select
    month_end_date,
    segment,
    beginning_arr,
    new_logo_arr,
    expansion_arr,
    reactivation_arr,
    contraction_arr,
    churn_arr,
    ending_arr,
    new_logo_arr + expansion_arr + reactivation_arr + contraction_arr + churn_arr as net_new_arr
from combined
