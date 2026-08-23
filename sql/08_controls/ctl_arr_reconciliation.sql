-- Build gate (PHASE1_SPEC 8.2). Any row this query returns is a reconciliation failure and
-- the build exits non-zero. An empty result set is PASS. Tolerance: $1.00.
--
-- Checks, at every grain the specification requires:
--   company_month          beginning + movements = ending, every month, company total
--   segment_month           same, every month, every segment
--   full_period              same, telescoped across FY2025 and across the full actual window
--   product_customer_tie   total ARR from fct_arr_product_movement = total ARR from
--                            fct_arr_movement, every month (categories do not tie; totals must)
with company_month as (
    select
        'company_month' as grain,
        month_end_date::varchar as grain_key,
        beginning_arr + new_logo_arr + expansion_arr + reactivation_arr
            + contraction_arr + churn_arr as implied_ending_arr,
        ending_arr
    from fct_arr_waterfall
    where segment = 'Total'
),

segment_month as (
    select
        'segment_month' as grain,
        segment || ' / ' || month_end_date::varchar as grain_key,
        beginning_arr + new_logo_arr + expansion_arr + reactivation_arr
            + contraction_arr + churn_arr as implied_ending_arr,
        ending_arr
    from fct_arr_waterfall
    where segment <> 'Total'
),

full_period_fy2025 as (
    select
        'full_period' as grain,
        'FY2025' as grain_key,
        (
            select beginning_arr from fct_arr_waterfall
            where segment = 'Total' and month_end_date = date '2025-01-31'
        ) + sum(new_logo_arr) + sum(expansion_arr) + sum(reactivation_arr)
          + sum(contraction_arr) + sum(churn_arr) as implied_ending_arr,
        (
            select ending_arr from fct_arr_waterfall
            where segment = 'Total' and month_end_date = date '2025-12-31'
        ) as ending_arr
    from fct_arr_waterfall
    where segment = 'Total' and month_end_date between date '2025-01-31' and date '2025-12-31'
),

full_period_all_actual as (
    select
        'full_period' as grain,
        'all_actual_months' as grain_key,
        (
            select beginning_arr from fct_arr_waterfall
            where segment = 'Total'
              and month_end_date = (select min(month_end_date) from dim_date where is_actual)
        ) + sum(new_logo_arr) + sum(expansion_arr) + sum(reactivation_arr)
          + sum(contraction_arr) + sum(churn_arr) as implied_ending_arr,
        (
            select ending_arr from fct_arr_waterfall
            where segment = 'Total'
              and month_end_date = (select max(month_end_date) from dim_date where is_actual)
        ) as ending_arr
    from fct_arr_waterfall
    where segment = 'Total'
      and month_end_date in (select month_end_date from dim_date where is_actual)
),

product_customer_tie as (
    select
        'product_customer_tie' as grain,
        pm.month_end_date::varchar as grain_key,
        pm.total_product_arr as implied_ending_arr,
        cm.total_customer_arr as ending_arr
    from (
        select month_end_date, sum(end_arr) as total_product_arr
        from fct_arr_product_movement
        group by 1
    ) pm
    join (
        select month_end_date, sum(end_arr) as total_customer_arr
        from fct_arr_movement
        group by 1
    ) cm on cm.month_end_date = pm.month_end_date
),

all_checks as (
    select * from company_month
    union all
    select * from segment_month
    union all
    select * from full_period_fy2025
    union all
    select * from full_period_all_actual
    union all
    select * from product_customer_tie
)

select
    grain,
    grain_key,
    implied_ending_arr,
    ending_arr,
    implied_ending_arr - ending_arr as diff
from all_checks
where abs(implied_ending_arr - ending_arr) >= 1.00
order by grain, grain_key
