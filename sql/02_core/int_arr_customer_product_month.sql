-- Dense customer x product x month ARR state.
--
-- fact_subscription_monthly is sparse: a customer-product pair has rows only in the months it
-- was live. Before any LAG() runs, we build a dense spine per (customer_id, product_id) pair
-- covering every month from that pair's first appearance through the last month present in the
-- source data, filling missing months with zero ARR. Without this, LAG() would silently compare
-- non-adjacent months and turn a dropped-then-re-added module into a false expansion.
--
-- This model feeds fct_arr_product_movement only. It is NOT the customer-grain aggregation
-- point -- that is int_arr_customer_month, which sums across products before it lags anything
-- (PHASE1_SPEC 8.2).
--
-- DuckDB note: `rows between unbounded preceding and 1 preceding` is standard SQL window
-- framing and is portable to Snowflake and Databricks unchanged.

with product_state as (
    select
        customer_id,
        product_id,
        month_end_date,
        sum(seats) as seats,
        sum(mrr)   as mrr,
        sum(arr)   as arr
    from stg_fact_subscription_monthly
    group by 1, 2, 3
),

pair_window as (
    select
        customer_id,
        product_id,
        min(month_end_date) as first_month
    from product_state
    group by 1, 2
),

last_reporting_month as (
    select max(month_end_date) as month_end_date
    from stg_fact_subscription_monthly
),

spine as (
    select
        pw.customer_id,
        pw.product_id,
        d.month_end_date
    from pair_window pw
    join stg_dim_date d
        on d.month_end_date between pw.first_month and (select month_end_date from last_reporting_month)
),

dense as (
    select
        s.customer_id,
        s.product_id,
        s.month_end_date,
        coalesce(ps.seats, 0) as seats,
        coalesce(ps.mrr, 0)   as mrr,
        coalesce(ps.arr, 0)   as arr
    from spine s
    left join product_state ps
        on ps.customer_id = s.customer_id
       and ps.product_id = s.product_id
       and ps.month_end_date = s.month_end_date
)

select
    customer_id,
    product_id,
    month_end_date,
    seats,
    arr as end_arr,
    coalesce(
        lag(arr) over (partition by customer_id, product_id order by month_end_date),
        0
    ) as beg_arr,
    coalesce(
        max(case when arr > 0 then 1 else 0 end) over (
            partition by customer_id, product_id order by month_end_date
            rows between unbounded preceding and 1 preceding
        ),
        0
    ) as had_positive_arr_before
from dense
