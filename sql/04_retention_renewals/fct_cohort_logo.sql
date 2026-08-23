-- Quarterly acquisition cohort logo retention (PHASE1_SPEC 6.2). Same grain and cohort
-- construction as fct_cohort_arr; kept as a separate model per PHASE1_SPEC 6.2's own naming
-- rather than folding logo counts into the ARR cohort table.
--
-- A logo survives a cohort period if it has ARR > 0 at that quarter-end -- a customer who
-- churned and later reactivated from OUTSIDE this cohort's own membership is not double-counted
-- here; int_cohort_quarterly tracks each original cohort member's own ARR through time, not
-- "any customer active this quarter."
with by_segment as (
    select
        acquisition_quarter,
        segment,
        quarters_since_acquisition,
        count(distinct customer_id) as cohort_logo_count,
        sum(case when arr > 0 then 1 else 0 end) as surviving_logos
    from int_cohort_quarterly
    group by 1, 2, 3
),

by_company as (
    select
        acquisition_quarter,
        'Total' as segment,
        quarters_since_acquisition,
        count(distinct customer_id) as cohort_logo_count,
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
    select acquisition_quarter, segment, cohort_logo_count as starting_logos
    from combined
    where quarters_since_acquisition = 0
)

select
    c.acquisition_quarter,
    c.segment,
    c.quarters_since_acquisition,
    s.starting_logos,
    c.surviving_logos,
    c.surviving_logos::double / nullif(s.starting_logos, 0) as logo_retention_pct
from combined c
join starting s
    on s.acquisition_quarter = c.acquisition_quarter and s.segment = c.segment
order by acquisition_quarter, segment, quarters_since_acquisition
