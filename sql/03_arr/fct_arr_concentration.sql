-- Customer concentration by month: top-10 and largest-customer share of total ARR.
with ranked as (
    select
        month_end_date,
        customer_id,
        arr,
        row_number() over (partition by month_end_date order by arr desc, customer_id) as arr_rank
    from fct_arr_snapshot
    where arr > 0
),

totals as (
    select month_end_date, sum(arr) as total_arr
    from fct_arr_snapshot
    group by 1
),

top10 as (
    select month_end_date, sum(arr) as top10_arr
    from ranked
    where arr_rank <= 10
    group by 1
),

largest as (
    select month_end_date, arr as largest_customer_arr
    from ranked
    where arr_rank = 1
)

select
    t.month_end_date,
    t.total_arr,
    coalesce(top10.top10_arr, 0) as top10_arr,
    coalesce(top10.top10_arr, 0) / nullif(t.total_arr, 0) as top10_share,
    coalesce(largest.largest_customer_arr, 0) as largest_customer_arr,
    coalesce(largest.largest_customer_arr, 0) / nullif(t.total_arr, 0) as largest_customer_share
from totals t
left join top10 on top10.month_end_date = t.month_end_date
left join largest on largest.month_end_date = t.month_end_date
order by t.month_end_date
