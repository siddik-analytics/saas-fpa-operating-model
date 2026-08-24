-- Normalized management variance mart -- one row per headline metric, Board Budget vs.
-- Independent Base Reforecast, FY2026. This is the metric-level ranking and materiality table
-- the report's scorecard and the commentary engine's Executive Summary selection both read;
-- driver-level detail (which New Logo / OpEx / COGS line moved the number) lives in the
-- individual bridge fct_ models and is picked up separately by int_commentary_candidates.
--
-- Favorable/unfavorable polarity and materiality are NEVER re-derived here with an inline CASE
-- statement -- both come from the centralised config/commentary_rules.yml tables
-- (int_metric_polarity, int_materiality_thresholds), joined by metric name.
--
-- `unit` distinguishes usd / bps / fte so a percentage or rank is never computed across
-- incompatible scales (e.g. a $250k ARR variance and a 429 bps margin variance are not
-- comparable numbers) -- PHASE1_SPEC-analogous instruction: do not calculate a percentage
-- variance where the denominator semantics make it misleading.
with exit_arr as (
    select 'exit_arr' as metric, 'Exit ARR' as metric_label, 'Dec-2026' as period, 'usd' as unit,
           b.amount as budget_amount, e.amount as base_amount, 'fct_arr_budget_bridge' as source_model
    from fct_arr_budget_bridge b, fct_arr_budget_bridge e
    where b.segment = 'Total' and b.line_item = 'Budget Exit ARR'
      and e.segment = 'Total' and e.line_item = 'Base Reforecast Exit ARR'
),

new_logo_arr as (
    select 'new_logo_arr' as metric, 'New Logo ARR' as metric_label, 'FY2026' as period, 'usd' as unit,
           budget_amount, base_amount, 'int_budget_reforecast_comparison' as source_model
    from int_budget_reforecast_comparison
    where metric_group = 'arr' and metric = 'new_logo_arr' and segment = 'Total'
),

revenue as (
    select 'total_revenue' as metric, 'Revenue' as metric_label, 'FY2026' as period, 'usd' as unit,
           budget_amount, base_amount, 'int_budget_reforecast_comparison' as source_model
    from int_budget_reforecast_comparison
    where metric_group = 'revenue' and metric = 'total_revenue'
),

gross_profit as (
    select 'gross_profit' as metric, 'Gross Profit' as metric_label, 'FY2026' as period, 'usd' as unit,
           b.amount as budget_amount, e.amount as base_amount, 'fct_gross_profit_bridge' as source_model
    from fct_gross_profit_bridge b, fct_gross_profit_bridge e
    where b.line_item = 'Budget Gross Profit' and e.line_item = 'Base Gross Profit'
),

gross_margin as (
    select 'gross_margin_bps' as metric, 'Gross Margin' as metric_label, 'FY2026' as period, 'bps' as unit,
           b.amount * 10000 as budget_amount, e.amount * 10000 as base_amount, 'fct_gross_profit_bridge' as source_model
    from fct_gross_profit_bridge b, fct_gross_profit_bridge e
    where b.line_item = 'Budget Gross Margin %' and e.line_item = 'Base Gross Margin %'
),

sm as (
    select 'sales_marketing' as metric, 'Sales & Marketing' as metric_label, 'FY2026' as period, 'usd' as unit,
           budget_amount, base_amount, 'int_budget_reforecast_comparison' as source_model
    from int_budget_reforecast_comparison
    where metric_group = 'opex' and metric = 'sales_marketing'
),

rd as (
    select 'research_development' as metric, 'Research & Development' as metric_label, 'FY2026' as period, 'usd' as unit,
           budget_amount, base_amount, 'int_budget_reforecast_comparison' as source_model
    from int_budget_reforecast_comparison
    where metric_group = 'opex' and metric = 'research_development'
),

ga as (
    select 'general_administrative' as metric, 'General & Administrative' as metric_label, 'FY2026' as period, 'usd' as unit,
           budget_amount, base_amount, 'int_budget_reforecast_comparison' as source_model
    from int_budget_reforecast_comparison
    where metric_group = 'opex' and metric = 'general_administrative'
),

total_opex as (
    select 'total_opex' as metric, 'Total OpEx' as metric_label, 'FY2026' as period, 'usd' as unit,
           budget_amount, base_amount, 'int_budget_reforecast_comparison' as source_model
    from int_budget_reforecast_comparison
    where metric_group = 'opex' and metric = 'total_opex'
),

operating_income as (
    select 'operating_income' as metric, 'Operating Income / (Loss)' as metric_label, 'FY2026' as period, 'usd' as unit,
           b.amount as budget_amount, e.amount as base_amount, 'fct_operating_income_bridge' as source_model
    from fct_operating_income_bridge b, fct_operating_income_bridge e
    where b.line_item = 'Budget Operating Income / (Loss)' and e.line_item = 'Base Operating Income / (Loss)'
),

ending_headcount as (
    select 'ending_headcount' as metric, 'Ending Headcount' as metric_label, 'Dec-2026' as period, 'fte' as unit,
           budget_amount, base_amount, 'int_budget_reforecast_comparison' as source_model
    from int_budget_reforecast_comparison
    where metric_group = 'headcount' and metric = 'ending_headcount'
),

all_metrics as (
    select * from exit_arr union all select * from new_logo_arr union all select * from revenue
    union all select * from gross_profit union all select * from gross_margin
    union all select * from sm union all select * from rd union all select * from ga
    union all select * from total_opex union all select * from operating_income
    union all select * from ending_headcount
),

with_variance as (
    select
        m.*,
        m.base_amount - m.budget_amount as variance,
        case when m.unit = 'usd' and abs(m.budget_amount) > 0 then (m.base_amount - m.budget_amount) / abs(m.budget_amount)
             else null end as variance_pct
    from all_metrics m
),

with_polarity as (
    select v.*, p.polarity
    from with_variance v
    left join int_metric_polarity p on p.metric = v.metric
),

with_favorability as (
    select *,
        case
            when polarity = 'higher_favorable' then case when variance > 0 then 'Favorable' when variance < 0 then 'Unfavorable' else 'In line' end
            when polarity = 'lower_favorable' then case when variance < 0 then 'Favorable' when variance > 0 then 'Unfavorable' else 'In line' end
            when polarity = 'contextual' then 'N/A'
            else null
        end as favorable_unfavorable
    from with_polarity
),

thresholds as (
    select metric,
           max(case when threshold_name = 'abs_usd' then threshold_value end) as abs_usd,
           max(case when threshold_name = 'pct' then threshold_value end) as pct,
           max(case when threshold_name = 'bps' then threshold_value end) as bps,
           max(case when threshold_name = 'fte' then threshold_value end) as fte
    from int_materiality_thresholds
    group by 1
),

with_materiality as (
    select w.*, t.abs_usd, t.pct, t.bps, t.fte,
        case
            when t.abs_usd is not null and abs(w.variance) >= t.abs_usd then true
            when t.pct is not null and w.variance_pct is not null and abs(w.variance_pct) >= t.pct then true
            when t.bps is not null and w.unit = 'bps' and abs(w.variance) >= t.bps then true
            when t.fte is not null and w.unit = 'fte' and abs(w.variance) >= t.fte then true
            else false
        end as materiality_flag
    from with_favorability w
    left join thresholds t on t.metric = w.metric
),

ranked as (
    select *,
        rank() over (partition by unit order by abs(variance) desc) as rank_abs_variance
    from with_materiality
)

select
    metric, metric_label, period, 'FY2026 Board Budget vs Base Reforecast' as comparison,
    null as driver, null as driver_category, unit,
    budget_amount, base_amount, base_amount as amount, variance, variance_pct,
    favorable_unfavorable, rank_abs_variance, materiality_flag, source_model
from ranked
order by unit, rank_abs_variance
