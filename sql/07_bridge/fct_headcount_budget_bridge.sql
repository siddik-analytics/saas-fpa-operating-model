-- Dec-2026 Ending Headcount: Board Budget vs. Independent Base Reforecast.
--
-- fact_budget's headcount memo row (account 9200, "Ending Headcount") posts a single
-- company-level statistical figure every month, with no functional or segmental breakdown
-- (docs/data_dictionary.md) -- there is no Budget hiring plan by function in the source data to
-- bridge against. Per the explicit instruction, the bridge is therefore kept at the highest
-- grain the Budget side actually supports (`section = 'company_bridge'`), and Base's own
-- ending headcount by function -- real, segment-native, from fct_headcount_forecast -- is
-- provided separately (`section = 'base_by_function'`) so a reader can see WHERE Base's own
-- headcount lands even though it cannot be tied back to Budget's own (unobserved) functional
-- assumption. No Budget functional split is fabricated to close this gap.
with company_bridge as (
    select 'company_bridge' as section, 'Company' as grain_key, 1 as line_order,
           'Budget Ending Headcount' as line_item, budget_amount as amount
    from int_budget_reforecast_comparison
    where metric_group = 'headcount' and metric = 'ending_headcount'
    union all
    select 'company_bridge', 'Company', 2,
           'Net headcount variance (driver detail not supported at Budget''s grain -- fact_budget account 9200 carries no functional breakdown)',
           base_amount - budget_amount
    from int_budget_reforecast_comparison
    where metric_group = 'headcount' and metric = 'ending_headcount'
    union all
    select 'company_bridge', 'Company', 3, 'Base Ending Headcount', base_amount
    from int_budget_reforecast_comparison
    where metric_group = 'headcount' and metric = 'ending_headcount'
),

base_by_function as (
    select
        'base_by_function' as section, f.function as grain_key, null::integer as line_order,
        null as line_item,
        beg.ending_headcount as beginning_headcount_jun2026,
        sum(f.hires) as h2_hires,
        sum(f.departures) as h2_departures,
        max(case when f.month_end_date = date '2026-12-31' then f.ending_headcount end) as ending_headcount_dec2026
    from fct_headcount_forecast f
    join (select function, ending_headcount from fct_headcount_forecast
          where path = 'Base' and month_end_date = date '2026-06-30') beg
        on beg.function = f.function
    where f.path = 'Base' and f.month_end_date between date '2026-07-31' and date '2026-12-31'
    group by 1, 2, 4, beg.ending_headcount
),

base_by_function_total as (
    select 'base_by_function' as section, 'Total' as grain_key, null::integer as line_order, null as line_item,
           sum(beginning_headcount_jun2026) as beginning_headcount_jun2026,
           sum(h2_hires) as h2_hires, sum(h2_departures) as h2_departures,
           sum(ending_headcount_dec2026) as ending_headcount_dec2026
    from base_by_function
)

select section, grain_key, line_order, line_item, amount,
       null::double as beginning_headcount_jun2026, null::double as h2_hires,
       null::double as h2_departures, null::double as ending_headcount_dec2026
from company_bridge
union all
select section, grain_key, line_order, line_item, null::double as amount,
       beginning_headcount_jun2026, h2_hires, h2_departures, ending_headcount_dec2026
from base_by_function
union all
select section, grain_key, line_order, line_item, null::double as amount,
       beginning_headcount_jun2026, h2_hires, h2_departures, ending_headcount_dec2026
from base_by_function_total
order by section, line_order, grain_key
