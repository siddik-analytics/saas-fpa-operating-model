-- Normalized commentary evidence -- one row per NUMERIC FACT referenced anywhere in a
-- `fct_commentary_output` row's headline / detail / supporting_evidence / management_implication
-- text, independently re-derived here from the same underlying bridge / diagnostic / policy /
-- hiring models rather than parsed back out of the generated text.
--
-- This is the traceability guarantee the report actually makes (see docs/bridge_commentary.md
-- and the report's own section 13 preamble): `driver_1_amount` / `driver_2_amount` on
-- `fct_commentary_output` cover only the one or two headline drivers a row foregrounds, and
-- several commentary rows embed more than two numeric facts (e.g. Exit ARR's top + secondary +
-- offset drivers, or the Hiring row's Dec-2026 AND Dec-2027 figures). Every one of those facts
-- gets its own row here, and `ctl_bridge_commentary` check I validates against THIS table, not
-- against the two driver columns alone.
--
-- Grain: (commentary_id, evidence_label). `commentary_id` is looked up from
-- `fct_commentary_output` by `metric`, which is unique per generated row (one row per headline
-- metric, plus exactly one Runway, one Hiring and one Segment row).
with commentary_ids as (
    select commentary_id, metric from fct_commentary_output
),

-- ============================================================================
-- Exit ARR
-- ============================================================================
arr_diag as (select * from fct_new_logo_diagnosis where segment = 'Total'),
arr_top as (select * from int_commentary_candidates where headline_metric = 'exit_arr' and rank_abs_amount = 1),
arr_offset as (select * from int_commentary_candidates where headline_metric = 'exit_arr' and is_material_offset limit 1),
arr_secondary as (select * from int_commentary_candidates where headline_metric = 'exit_arr' and is_material_secondary_same_direction),
arr_mv as (select variance from fct_management_variance where metric = 'exit_arr'),

exit_arr_evidence as (
    select 'exit_arr' as metric, 'headline_variance' as evidence_label, variance as evidence_amount, 'fct_management_variance' as source_model
    from arr_mv
    union all
    select 'exit_arr', 'top_driver_amount', amount, 'fct_arr_budget_bridge' from arr_top
    union all
    select 'exit_arr', 'secondary_unfavorable_driver_amount', amount, 'fct_arr_budget_bridge' from arr_secondary
    union all
    select 'exit_arr', 'offset_driver_amount', amount, 'fct_arr_budget_bridge' from arr_offset
    union all
    select 'exit_arr', 'h2_pipeline_bound_months', h2_pipeline_bound_months, 'fct_new_logo_diagnosis' from arr_diag
    union all
    select 'exit_arr', 'h2_segment_months', h2_segment_months, 'fct_new_logo_diagnosis' from arr_diag
),

-- ============================================================================
-- New Logo ARR
-- ============================================================================
new_logo_mv as (select variance from fct_management_variance where metric = 'new_logo_arr'),

new_logo_evidence as (
    select 'new_logo_arr' as metric, 'headline_variance' as evidence_label, variance as evidence_amount, 'fct_management_variance' as source_model
    from new_logo_mv
    union all
    select 'new_logo_arr', 'h2_pipeline_bound_months', h2_pipeline_bound_months, 'fct_new_logo_diagnosis' from arr_diag
    union all
    select 'new_logo_arr', 'h2_segment_months', h2_segment_months, 'fct_new_logo_diagnosis' from arr_diag
    union all
    select 'new_logo_arr', 'h2_capacity_bound_months', h2_capacity_bound_months, 'fct_new_logo_diagnosis' from arr_diag
    union all
    select 'new_logo_arr', 'h2_pipeline_supported_arr', h2_pipeline_supported_arr, 'fct_new_logo_diagnosis' from arr_diag
    union all
    select 'new_logo_arr', 'h2_capacity_supported_arr', h2_capacity_supported_arr, 'fct_new_logo_diagnosis' from arr_diag
    union all
    select 'new_logo_arr', 'h2_constrained_new_logo_arr', h2_constrained_new_logo_arr, 'fct_new_logo_diagnosis' from arr_diag
),

-- ============================================================================
-- Revenue
-- ============================================================================
rev_top as (select * from int_commentary_candidates where headline_metric = 'total_revenue' and rank_abs_amount = 1),
rev_mv as (select variance from fct_management_variance where metric = 'total_revenue'),

revenue_evidence as (
    select 'total_revenue' as metric, 'headline_variance' as evidence_label, variance as evidence_amount, 'fct_management_variance' as source_model
    from rev_mv
    union all
    select 'total_revenue', 'top_driver_amount', amount, 'fct_revenue_budget_bridge' from rev_top
),

-- ============================================================================
-- Gross Profit / Gross Margin
-- ============================================================================
gp_cogs as (
    select
        sum(case when line_item like 'Subscription COGS%' then amount else 0 end) as sub_cogs_impact,
        sum(case when line_item like 'Services COGS%' then amount else 0 end) as svc_cogs_impact
    from fct_gross_profit_bridge
    where unit = 'usd' and line_order between 3 and 6
),
gp_mv as (select variance from fct_management_variance where metric = 'gross_profit'),
gp_margin as (select variance as margin_bps_variance from fct_management_variance where metric = 'gross_margin_bps'),
gp_rev as (select variance as revenue_variance from fct_management_variance where metric = 'total_revenue'),

gross_profit_evidence as (
    select 'gross_profit' as metric, 'headline_variance' as evidence_label, variance as evidence_amount, 'fct_management_variance' as source_model
    from gp_mv
    union all
    select 'gross_profit', 'margin_bps_variance', margin_bps_variance, 'fct_management_variance' from gp_margin
    union all
    select 'gross_profit', 'revenue_variance', revenue_variance, 'fct_management_variance' from gp_rev
    union all
    select 'gross_profit', 'subscription_cogs_impact', sub_cogs_impact, 'fct_gross_profit_bridge' from gp_cogs
    union all
    select 'gross_profit', 'services_cogs_impact', svc_cogs_impact, 'fct_gross_profit_bridge' from gp_cogs
),

-- ============================================================================
-- OpEx
-- ============================================================================
opex_top as (select * from int_commentary_candidates where headline_metric = 'total_opex' and rank_abs_amount = 1),
opex_mv as (select variance from fct_management_variance where metric = 'total_opex'),

opex_evidence as (
    select 'total_opex' as metric, 'headline_variance' as evidence_label, variance as evidence_amount, 'fct_management_variance' as source_model
    from opex_mv
    union all
    select 'total_opex', 'top_driver_amount', amount, 'fct_opex_budget_bridge' from opex_top
),

-- ============================================================================
-- Operating Income / Loss
-- ============================================================================
oi_top as (select * from int_commentary_candidates where headline_metric = 'operating_income' and rank_abs_amount = 1),
oi_mv as (select variance from fct_management_variance where metric = 'operating_income'),

oi_evidence as (
    select 'operating_income' as metric, 'headline_variance' as evidence_label, variance as evidence_amount, 'fct_management_variance' as source_model
    from oi_mv
    union all
    select 'operating_income', 'top_driver_amount', amount, 'fct_operating_income_bridge' from oi_top
),

-- ============================================================================
-- Headcount
-- ============================================================================
hc_mv as (select variance from fct_management_variance where metric = 'ending_headcount'),

headcount_evidence as (
    select 'ending_headcount' as metric, 'headline_variance' as evidence_label, variance as evidence_amount, 'fct_management_variance' as source_model
    from hc_mv
),

-- ============================================================================
-- Runway
-- ============================================================================
runway_facts as (
    select
        max(case when path = 'Base' then policy_runway_months end) as base_runway,
        max(case when path = 'Base' then headroom_months end) as base_headroom,
        max(case when path = 'Bear' then policy_runway_months end) as bear_runway,
        max(case when path = 'Bear' then headroom_months end) as bear_headroom,
        max(case when path = 'Bull' then policy_runway_months end) as bull_runway,
        max(case when path = 'Base_FullClose' then policy_runway_months end) as fullclose_runway,
        max(case when path = 'Base_FullClose' then headroom_months end) as fullclose_headroom,
        max(board_runway_floor_months) as floor_months
    from fct_cash_runway_policy
),

runway_evidence as (
    select 'policy_runway_months' as metric, unpivot_label as evidence_label, unpivot_value as evidence_amount, 'fct_cash_runway_policy' as source_model
    from runway_facts
    unpivot (unpivot_value for unpivot_label in (
        base_runway, base_headroom, bear_runway, bear_headroom, bull_runway,
        fullclose_runway, fullclose_headroom, floor_months
    ))
),

-- ============================================================================
-- Hiring decision
-- ============================================================================
hiring_facts as (
    select
        max(case when path = 'Base_FullClose' then policy_runway_months end) as fullclose_runway,
        max(case when path = 'Base_FullClose' then headroom_months end) as fullclose_headroom
    from fct_cash_runway_policy
),

hiring_scenario_facts as (
    select
        max(case when month_end_date = date '2026-12-31' then cumulative_hires end) as fullclose_hires,
        max(case when month_end_date = date '2026-12-31' then incremental_ending_arr end) as fullclose_incr_arr_2026,
        max(case when month_end_date = date '2026-12-31' then incremental_cash_impact end) as fullclose_incr_cash_2026,
        max(case when month_end_date = date '2027-12-31' then incremental_ending_arr end) as fullclose_incr_arr_2027,
        max(case when month_end_date = date '2027-12-31' then incremental_cash_impact end) as fullclose_incr_cash_2027,
        max(case when month_end_date = date '2027-12-31' then incremental_operating_income end) as fullclose_incr_oi_2027
    from fct_hiring_scenario
    where path = 'Base_FullClose' and month_end_date in (date '2026-12-31', date '2027-12-31')
),

targeted_facts as (
    select max(cumulative_hires) as targeted_hires
    from fct_hiring_scenario
    where path = 'Base_Targeted' and month_end_date = date '2026-12-31'
),

hiring_evidence as (
    select 'hiring_decision' as metric, unpivot_label as evidence_label, unpivot_value as evidence_amount, 'fct_hiring_scenario' as source_model
    from (select * from hiring_facts cross join hiring_scenario_facts cross join targeted_facts)
    unpivot (unpivot_value for unpivot_label in (
        fullclose_hires, fullclose_incr_arr_2026, fullclose_incr_cash_2026,
        fullclose_incr_arr_2027, fullclose_incr_cash_2027, fullclose_incr_oi_2027, targeted_hires
    ))
    union all
    select 'hiring_decision', 'fullclose_runway', fullclose_runway, 'fct_cash_runway_policy' from hiring_facts
    union all
    select 'hiring_decision', 'fullclose_headroom', fullclose_headroom, 'fct_cash_runway_policy' from hiring_facts
    union all
    select 'hiring_decision', 'h2_pipeline_bound_months', h2_pipeline_bound_months, 'fct_new_logo_diagnosis' from arr_diag
    union all
    select 'hiring_decision', 'h2_segment_months', h2_segment_months, 'fct_new_logo_diagnosis' from arr_diag
),

-- ============================================================================
-- Segment
-- ============================================================================
segment_variance as (
    select segment, base_amount - budget_amount as variance
    from int_budget_reforecast_comparison
    where metric_group = 'arr' and metric = 'ending_arr' and segment <> 'Total'
),
segment_ranked as (select *, rank() over (order by abs(variance) desc) as rnk from segment_variance),
segment_top_driver as (
    select c.* from int_commentary_candidates c
    join segment_ranked r on r.rnk = 1 and c.headline_metric = 'segment_arr_' || r.segment
    where c.rank_abs_amount = 1
),

segment_evidence as (
    select 'segment_arr' as metric, 'headline_variance' as evidence_label, r.variance as evidence_amount, 'int_budget_reforecast_comparison' as source_model
    from segment_ranked r where r.rnk = 1
    union all
    select 'segment_arr', 'top_driver_amount', t.amount, 'fct_arr_budget_bridge'
    from segment_top_driver t
),

all_evidence as (
    select * from exit_arr_evidence
    union all select * from new_logo_evidence
    union all select * from revenue_evidence
    union all select * from gross_profit_evidence
    union all select * from opex_evidence
    union all select * from oi_evidence
    union all select * from headcount_evidence
    union all select * from runway_evidence
    union all select * from hiring_evidence
    union all select * from segment_evidence
)

select
    ci.commentary_id, e.metric, e.evidence_label, e.evidence_amount, e.source_model
from all_evidence e
join commentary_ids ci on ci.metric = e.metric
where e.evidence_amount is not null
order by ci.commentary_id, e.evidence_label
