-- Customer-month ARR state -- the mandatory aggregation point (PHASE1_SPEC 8.2, binding).
--
-- Product-grain ARR is summed to customer grain FIRST, and only then is a dense customer-month
-- spine built and LAG() taken. This is what makes a same-month product swap (e.g. $30k moving
-- from Helio Dispatch to Helio Core) invisible here: total customer ARR is unchanged, so
-- beg_arr = end_arr and the customer classifies as No Change downstream in fct_arr_movement,
-- never as an artificial expansion plus an artificial contraction.
--
-- The dense spine runs from each customer's own first subscription month through the last
-- month present in the source data, so a churned customer keeps classifying (correctly, as
-- No Change once beg_arr = end_arr = 0) in every subsequent month, and a reactivation is
-- visible as a real gap rather than an adjacent-row artifact.
--
-- had_positive_arr_before: true if the customer had ARR > 0 in ANY month strictly before the
-- current one. This is what distinguishes New Logo (never positive before) from Reactivation
-- (was positive, dropped to zero, came back) under beg_arr = 0, end_arr > 0.

with customer_state as (
    select
        customer_id,
        month_end_date,
        sum(seats) as seats,
        sum(mrr)   as mrr,
        sum(arr)   as arr
    from stg_fact_subscription_monthly
    group by 1, 2
),

customer_window as (
    select customer_id, min(month_end_date) as first_month
    from customer_state
    group by 1
),

last_reporting_month as (
    select max(month_end_date) as month_end_date
    from stg_fact_subscription_monthly
),

spine as (
    select
        cw.customer_id,
        d.month_end_date
    from customer_window cw
    join stg_dim_date d
        on d.month_end_date between cw.first_month and (select month_end_date from last_reporting_month)
),

dense as (
    select
        s.customer_id,
        s.month_end_date,
        coalesce(cs.seats, 0) as seats,
        coalesce(cs.arr, 0)   as arr
    from spine s
    left join customer_state cs
        on cs.customer_id = s.customer_id
       and cs.month_end_date = s.month_end_date
)

select
    d.customer_id,
    c.segment,
    d.month_end_date,
    d.seats,
    d.arr as end_arr,
    coalesce(
        lag(d.arr) over (partition by d.customer_id order by d.month_end_date),
        0
    ) as beg_arr,
    coalesce(
        max(case when d.arr > 0 then 1 else 0 end) over (
            partition by d.customer_id order by d.month_end_date
            rows between unbounded preceding and 1 preceding
        ),
        0
    ) as had_positive_arr_before
from dense d
join dim_customer c on c.customer_id = d.customer_id
