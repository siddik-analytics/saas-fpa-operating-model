-- TTM NRR, GRR and logo retention -- the engine (PHASE1_SPEC 8.3). Grain: month_end_date x
-- segment, where segment is 'SMB' / 'Mid-Market' / 'Enterprise' for the segment-level rows and
-- 'Total' for the company-level rollup, matching fct_arr_waterfall's convention. A pure
-- aggregate of int_retention_cohort_customer_month; classification of cohort membership stays
-- customer-grain and happens upstream.
--
-- NRR = cohort_current_arr / cohort_beginning_arr. Includes expansion, contraction, churn and
-- reactivation of cohort members; can exceed 100%.
--
-- GRR = cohort_grr_arr / cohort_beginning_arr, where cohort_grr_arr sums a PER-CUSTOMER cap
-- (LEAST(current_arr, beginning_arr), applied in int_retention_cohort_customer_month before this
-- aggregation) -- never an aggregate-level cap. This is what keeps GRR <= 100% and GRR <= NRR
-- (ctl_retention_bounds).
--
-- Logo retention = retained_logos / cohort_customers, where retained_logos counts only original
-- cohort members with ARR > 0 at M -- a reactivation from OUTSIDE the M-12 cohort is not counted
-- as a retained logo here.
with by_segment as (
    select
        month_end_date,
        segment,
        count(*) as cohort_customers,
        sum(beginning_arr) as cohort_beginning_arr,
        sum(current_arr) as cohort_current_arr,
        sum(grr_customer_arr) as cohort_grr_arr,
        sum(is_retained_logo) as retained_logos
    from int_retention_cohort_customer_month
    group by 1, 2
),

by_company as (
    select
        month_end_date,
        'Total' as segment,
        count(*) as cohort_customers,
        sum(beginning_arr) as cohort_beginning_arr,
        sum(current_arr) as cohort_current_arr,
        sum(grr_customer_arr) as cohort_grr_arr,
        sum(is_retained_logo) as retained_logos
    from int_retention_cohort_customer_month
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
    cohort_customers,
    cohort_beginning_arr,
    cohort_current_arr,
    cohort_grr_arr,
    retained_logos,
    cohort_current_arr / nullif(cohort_beginning_arr, 0) as nrr,
    cohort_grr_arr / nullif(cohort_beginning_arr, 0) as grr,
    retained_logos::double / nullif(cohort_customers, 0) as logo_retention
from combined
order by month_end_date, segment
