-- Customer-grain TTM retention cohort -- the mandatory aggregation point for NRR, GRR and logo
-- retention (PHASE1_SPEC 8.3), mirroring the customer-grain-first pattern int_arr_customer_month
-- established for ARR movement (PHASE1_SPEC 8.2). fct_retention_ttm is a pure aggregate of the
-- rows built here; nothing computes NRR/GRR/logo retention straight off a segment-level total.
--
-- Cohort membership for reporting month M: a customer with ARR > 0 exactly 12 months earlier
-- (M-12), per the binding PHASE1_SPEC definition. A customer acquired after M-12 has no positive
-- ARR at M-12 -- no row yet in int_arr_customer_month, or a zero-ARR row -- and is therefore
-- excluded from both the numerator and the denominator. Trailing-twelve-month new logos never
-- enter a TTM cohort, by construction of this join, not by a separate filter.
--
-- M-12 is found by joining dim_date to itself 12 calendar rows apart (row_number lag), rather
-- than by date-interval arithmetic, so short months and DuckDB's own interval rules cannot shift
-- the lookback by a day. Only actual reporting months are eligible as M; M-12 does not itself
-- need to be an actual month (the opening balance month, 2023-12-31, is a valid M-12 for the
-- first TTM cohort, M = 2024-12-31).
with calendar as (
    select month_end_date, row_number() over (order by month_end_date) as month_seq
    from dim_date
),

lookback as (
    select
        m.month_end_date as reporting_month,
        m12.month_end_date as cohort_month
    from calendar m
    join calendar m12 on m12.month_seq = m.month_seq - 12
    join dim_date d on d.month_end_date = m.month_end_date
    where d.is_actual
),

cohort_membership as (
    select
        lb.reporting_month,
        lb.cohort_month,
        c12.customer_id,
        c12.segment,
        c12.end_arr as beginning_arr
    from lookback lb
    join int_arr_customer_month c12
        on c12.month_end_date = lb.cohort_month
       and c12.end_arr > 0
)

select
    cm.customer_id,
    cm.segment,
    cm.reporting_month as month_end_date,
    cm.cohort_month,
    cm.beginning_arr,
    coalesce(cur.end_arr, 0) as current_arr,
    least(coalesce(cur.end_arr, 0), cm.beginning_arr) as grr_customer_arr,
    case when coalesce(cur.end_arr, 0) > 0 then 1 else 0 end as is_retained_logo
from cohort_membership cm
left join int_arr_customer_month cur
    on cur.customer_id = cm.customer_id
   and cur.month_end_date = cm.reporting_month
