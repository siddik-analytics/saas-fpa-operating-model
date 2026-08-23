-- Customer-grain quarterly acquisition cohort: one row per customer x quarter-end, from the
-- customer's own acquisition quarter (quarters_since_acquisition = 0) through the last actual
-- quarter. Feeds fct_cohort_arr and fct_cohort_logo. Monthly cohort granularity is explicitly
-- out of scope (PHASE1_SPEC 13); this is the acquisition-quarter x quarters-since-acquisition
-- grain PHASE1_SPEC 6.2 calls for.
--
-- quarters_since_acquisition is computed from whole months between quarter-start dates (always
-- an exact multiple of 3), not date_diff('quarter', ...), so the arithmetic is portable to a
-- warehouse whose DATEDIFF does not support a quarter part.
with customer_cohort as (
    select
        customer_id,
        segment,
        date_trunc('quarter', acquisition_date) as acquisition_quarter_start,
        year(acquisition_date)::varchar || 'Q' || (((month(acquisition_date) - 1) // 3) + 1)::varchar
            as acquisition_quarter
    from dim_customer
),

quarter_ends as (
    select distinct
        month_end_date as quarter_end_date,
        date_trunc('quarter', month_end_date) as quarter_start
    from dim_date
    where is_quarter_end and is_actual
),

eligible as (
    select
        cc.customer_id,
        cc.segment,
        cc.acquisition_quarter,
        cc.acquisition_quarter_start,
        qe.quarter_end_date,
        date_diff('month', cc.acquisition_quarter_start, qe.quarter_start) // 3 as quarters_since_acquisition
    from customer_cohort cc
    join quarter_ends qe
        on qe.quarter_start >= cc.acquisition_quarter_start
)

select
    e.acquisition_quarter,
    e.acquisition_quarter_start,
    e.segment,
    e.customer_id,
    e.quarter_end_date,
    e.quarters_since_acquisition,
    coalesce(m.end_arr, 0) as arr
from eligible e
left join int_arr_customer_month m
    on m.customer_id = e.customer_id
   and m.month_end_date = e.quarter_end_date
