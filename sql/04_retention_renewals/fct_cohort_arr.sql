-- Quarterly acquisition cohort ARR retention (PHASE1_SPEC 6.2). Grain: acquisition_quarter x
-- segment x quarters_since_acquisition, where segment = 'Total' is the company rollup, matching
-- fct_arr_waterfall's convention. Feeds a Power BI cohort heatmap; monthly cohort granularity is
-- explicitly out of scope (PHASE1_SPEC 13).
--
-- starting_arr is the cohort's own ARR at quarters_since_acquisition = 0 (its acquisition
-- quarter-end, not day-of-signing ARR -- standard cohort convention). arr_retention_pct already
-- reflects net expansion, contraction, churn and reactivation within the cohort, so it is a
-- cohort-level analogue of NRR, not a capped GRR-style figure -- PHASE1_SPEC 7 calls for "cohort
-- NRR where appropriate," and this ratio is it.
with by_segment as (
    select
        acquisition_quarter,
        segment,
        quarters_since_acquisition,
        sum(arr) as period_arr,
        sum(case when arr > 0 then 1 else 0 end) as surviving_logos
    from int_cohort_quarterly
    group by 1, 2, 3
),

by_company as (
    select
        acquisition_quarter,
        'Total' as segment,
        quarters_since_acquisition,
        sum(arr) as period_arr,
        sum(case when arr > 0 then 1 else 0 end) as surviving_logos
    from int_cohort_quarterly
    group by 1, 3
),

combined as (
    select * from by_segment
    union all
    select * from by_company
),

starting as (
    select acquisition_quarter, segment, period_arr as starting_arr
    from combined
    where quarters_since_acquisition = 0
)

select
    c.acquisition_quarter,
    c.segment,
    c.quarters_since_acquisition,
    s.starting_arr,
    c.period_arr as retained_arr,
    c.period_arr / nullif(s.starting_arr, 0) as arr_retention_pct
from combined c
join starting s
    on s.acquisition_quarter = c.acquisition_quarter and s.segment = c.segment
order by acquisition_quarter, segment, quarters_since_acquisition
