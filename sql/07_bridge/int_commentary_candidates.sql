-- Driver-level ranking, one row per (headline metric, driver line), read from the bridge fct_
-- models' own delta lines (never the anchor/total rows). This is what lets the commentary
-- engine identify "the largest unfavorable driver," compute a driver's share of total absolute
-- variance (the data behind the word "primarily"), detect an opposite-signed offsetting driver,
-- and -- generically, for any headline metric, never hardcoded to a named driver -- detect a
-- material SECOND driver pushing in the SAME direction as the headline variance (the data
-- behind "another material unfavorable driver"). All deterministic, from calculated fields,
-- never eyeballed.
with driver_lines as (
    select 'exit_arr' as headline_metric, line_item as driver, driver_category, amount
    from fct_arr_budget_bridge
    where segment = 'Total' and line_order between 3 and 7
    union all
    select 'segment_arr_' || segment, line_item, driver_category, amount
    from fct_arr_budget_bridge
    where segment <> 'Total' and line_order between 3 and 7
    union all
    select 'total_revenue', 'Subscription: ' || line_item, 'revenue', amount
    from fct_revenue_budget_bridge
    where revenue_line = 'Subscription Revenue' and line_order between 2 and 4
    union all
    select 'total_revenue', 'Services: ' || line_item, 'revenue', amount
    from fct_revenue_budget_bridge
    where revenue_line = 'Services Revenue' and line_order between 2 and 4
    union all
    select 'gross_profit', line_item, 'margin', amount
    from fct_gross_profit_bridge
    where unit = 'usd' and line_order between 2 and 6
    union all
    select 'total_opex', line_item, 'opex', amount
    from fct_opex_budget_bridge
    where category = 'Total OpEx' and line_order between 2 and 4
    union all
    select 'operating_income', line_item, 'operating_income', amount
    from fct_operating_income_bridge
    where line_order between 2 and 8
),

headline_variance as (
    select metric as headline_metric, variance as headline_variance
    from fct_management_variance
    where unit = 'usd'
    union all
    select 'segment_arr_' || segment, base_amount - budget_amount
    from int_budget_reforecast_comparison
    where metric_group = 'arr' and metric = 'ending_arr' and segment <> 'Total'
),

-- Materiality threshold reused generically from the SAME centralised table every headline
-- metric's own materiality is judged against (int_materiality_thresholds, config/commentary_
-- rules.yml) -- a driver is not "material" by a separate, driver-specific rule invented here.
metric_abs_threshold as (
    select metric, threshold_value as abs_usd
    from int_materiality_thresholds
    where threshold_name = 'abs_usd'
),

with_shares as (
    select
        d.headline_metric, d.driver, d.driver_category, d.amount,
        h.headline_variance,
        abs(d.amount) / nullif(sum(abs(d.amount)) over (partition by d.headline_metric), 0) as share_of_total_abs_variance,
        rank() over (partition by d.headline_metric order by abs(d.amount) desc) as rank_abs_amount,
        case
            when sign(d.amount) <> sign(h.headline_variance) and sign(d.amount) <> 0 and sign(h.headline_variance) <> 0
            then true else false
        end as opposite_sign_to_headline,
        case
            when sign(d.amount) = sign(h.headline_variance) and sign(d.amount) <> 0
            then true else false
        end as same_sign_as_headline,
        t.abs_usd as headline_metric_abs_threshold
    from driver_lines d
    join headline_variance h on h.headline_metric = d.headline_metric
    left join metric_abs_threshold t on t.metric = d.headline_metric
),

with_same_sign_rank as (
    select *,
        case when same_sign_as_headline
             then rank() over (partition by headline_metric, same_sign_as_headline order by abs(amount) desc)
             else null end as rank_same_sign_abs_amount
    from with_shares
)

select
    headline_metric, driver, driver_category, amount, headline_variance,
    share_of_total_abs_variance, rank_abs_amount, opposite_sign_to_headline, same_sign_as_headline,
    rank_same_sign_abs_amount,
    case when opposite_sign_to_headline
             and share_of_total_abs_variance >= (select value from int_commentary_params where param = 'offsetting_driver_share_threshold')
         then true else false end as is_material_offset,
    case when share_of_total_abs_variance >= (select value from int_commentary_params where param = 'primary_driver_share_threshold')
         then true else false end as is_primary_driver,
    -- The generic "second material driver pushing the same direction as the headline" flag:
    -- same-signed, ranked #2 among same-signed drivers (never the overall #2, which may be an
    -- opposite-signed offset instead -- see fct_arr_budget_bridge for exactly this case), and
    -- clearing the SAME abs-dollar materiality bar the headline metric itself is judged against.
    case when same_sign_as_headline
             and rank_same_sign_abs_amount = 2
             and headline_metric_abs_threshold is not null
             and abs(amount) >= headline_metric_abs_threshold
         then true else false end as is_material_secondary_same_direction
from with_same_sign_rank
order by headline_metric, rank_abs_amount
