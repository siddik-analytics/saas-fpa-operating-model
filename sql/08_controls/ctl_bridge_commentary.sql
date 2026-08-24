-- Build gate for Phase 7 (Board Budget -> Q2 Base reforecast bridges and deterministic
-- management commentary). Any row this query returns is a violation and the build exits
-- non-zero. An empty result set is PASS. Same grain / grain_key / implied_value / bound
-- convention as ctl_forecast_controls.sql.
--
--   A  arr_bridge_reconciles        fct_arr_budget_bridge residual = 0, every segment
--   B  segment_arr_sums_to_company  SMB + Mid-Market + Enterprise = Total, both the Budget and
--                                   Base anchor lines, fct_arr_budget_bridge
--   C  revenue_bridge_reconciles    fct_revenue_budget_bridge residual = 0, every revenue_line
--   D  gross_profit_bridge_reconciles  fct_gross_profit_bridge residual = 0 (dollar lines)
--   E  opex_bridge_reconciles       fct_opex_budget_bridge residual = 0, every category
--   F  operating_income_bridge_reconciles  fct_operating_income_bridge residual = 0
--   G  headcount_bridge_consistent  the company bridge's Base Ending Headcount equals Base's own
--                                   by-function total, fct_headcount_budget_bridge
--   H  no_plug_lines                no line item named Plug / Balancing / Unexplained Other in
--                                   any Phase 7 bridge model
--   I  commentary_traceable         every evidence_amount in fct_commentary_evidence -- the
--                                   normalized record of every numeric fact actually embedded in
--                                   a commentary row's text, not just the two driver_N_amount
--                                   columns -- matches a real stored amount in its own declared
--                                   source_model, tolerance $1
--   J  materiality_enforced         every non-mandatory-governance commentary row's metric is
--                                   flagged material in fct_management_variance
--   K  priority_valid               priority is one of the four documented values
--   L  no_duplicate_commentary_id   commentary_id is unique
--   M  polarity_consistent          fct_management_variance.favorable_unfavorable matches an
--                                   INDEPENDENT recomputation from int_metric_polarity + sign(variance)
--   N  top_driver_ranking_correct   int_commentary_candidates.rank_abs_amount matches an
--                                   independent re-rank by abs(amount) within headline_metric
--   O  allocated_segment_priority_capped  Segment-section commentary (allocated Budget grain)
--                                   never carries a priority above Medium, regardless of its
--                                   dollar size, so it cannot out-rank source-grain commentary
--                                   in the Executive Summary on dollar magnitude alone
--   P  every_commentary_row_has_evidence  every fct_commentary_output row has at least one
--                                   fct_commentary_evidence row (no row's numeric claims go
--                                   completely unchecked)
with arr_bridge_reconciles as (
    select 'arr_bridge_reconciles' as grain, segment as grain_key, residual as implied_value, 0.0 as bound
    from (select distinct segment, residual from fct_arr_budget_bridge) t
    where abs(residual) >= 1.00
),

segment_arr_sums_to_company as (
    select 'segment_arr_sums_to_company' as grain, 'budget_exit_arr' as grain_key,
           sum(case when segment <> 'Total' then amount else 0 end) as implied_value,
           sum(case when segment = 'Total' then amount else 0 end) as bound
    from fct_arr_budget_bridge
    where line_item = 'Budget Exit ARR'
    having abs(sum(case when segment <> 'Total' then amount else 0 end)
               - sum(case when segment = 'Total' then amount else 0 end)) >= 1.00
    union all
    select 'segment_arr_sums_to_company', 'base_exit_arr',
           sum(case when segment <> 'Total' then amount else 0 end),
           sum(case when segment = 'Total' then amount else 0 end)
    from fct_arr_budget_bridge
    where line_item = 'Base Reforecast Exit ARR'
    having abs(sum(case when segment <> 'Total' then amount else 0 end)
               - sum(case when segment = 'Total' then amount else 0 end)) >= 1.00
),

revenue_bridge_reconciles as (
    select 'revenue_bridge_reconciles' as grain, revenue_line as grain_key, residual as implied_value, 0.0 as bound
    from (select distinct revenue_line, residual from fct_revenue_budget_bridge) t
    where abs(residual) >= 1.00
),

gross_profit_bridge_reconciles as (
    select 'gross_profit_bridge_reconciles' as grain, 'company' as grain_key, residual as implied_value, 0.0 as bound
    from (select distinct residual from fct_gross_profit_bridge where unit = 'usd') t
    where abs(residual) >= 1.00
),

opex_bridge_reconciles as (
    select 'opex_bridge_reconciles' as grain, category as grain_key, residual as implied_value, 0.0 as bound
    from (select distinct category, residual from fct_opex_budget_bridge) t
    where abs(residual) >= 1.00
),

operating_income_bridge_reconciles as (
    select 'operating_income_bridge_reconciles' as grain, 'company' as grain_key, residual as implied_value, 0.0 as bound
    from (select distinct residual from fct_operating_income_bridge) t
    where abs(residual) >= 1.00
),

headcount_bridge_consistent as (
    select 'headcount_bridge_consistent' as grain, 'company_vs_function_total' as grain_key,
           cb.amount as implied_value, bf.ending_headcount_dec2026 as bound
    from fct_headcount_budget_bridge cb
    join fct_headcount_budget_bridge bf
        on bf.section = 'base_by_function' and bf.grain_key = 'Total'
    where cb.section = 'company_bridge' and cb.line_item = 'Base Ending Headcount'
      and abs(cb.amount - bf.ending_headcount_dec2026) >= 0.05
),

no_plug_lines as (
    select 'no_plug_lines' as grain, 'fct_arr_budget_bridge' as grain_key, count(*)::double as implied_value, 0.0 as bound
    from fct_arr_budget_bridge where regexp_matches(lower(line_item), 'plug|balancing|unexplained other')
    having count(*) > 0
    union all
    select 'no_plug_lines', 'fct_revenue_budget_bridge', count(*)::double, 0.0
    from fct_revenue_budget_bridge where regexp_matches(lower(line_item), 'plug|balancing|unexplained other')
    having count(*) > 0
    union all
    select 'no_plug_lines', 'fct_gross_profit_bridge', count(*)::double, 0.0
    from fct_gross_profit_bridge where regexp_matches(lower(line_item), 'plug|balancing|unexplained other')
    having count(*) > 0
    union all
    select 'no_plug_lines', 'fct_opex_budget_bridge', count(*)::double, 0.0
    from fct_opex_budget_bridge where regexp_matches(lower(line_item), 'plug|balancing|unexplained other')
    having count(*) > 0
    union all
    select 'no_plug_lines', 'fct_operating_income_bridge', count(*)::double, 0.0
    from fct_operating_income_bridge where regexp_matches(lower(line_item), 'plug|balancing|unexplained other')
    having count(*) > 0
),

source_amounts_pool as (
    select 'fct_arr_budget_bridge' as source_model, amount from fct_arr_budget_bridge
    union all select 'fct_new_logo_diagnosis', new_logo_arr_variance from fct_new_logo_diagnosis
    union all select 'fct_new_logo_diagnosis', h2_pipeline_supported_arr from fct_new_logo_diagnosis
    union all select 'fct_new_logo_diagnosis', h2_capacity_supported_arr from fct_new_logo_diagnosis
    union all select 'fct_new_logo_diagnosis', h2_constrained_new_logo_arr from fct_new_logo_diagnosis
    union all select 'fct_new_logo_diagnosis', h2_pipeline_bound_months from fct_new_logo_diagnosis
    union all select 'fct_new_logo_diagnosis', h2_capacity_bound_months from fct_new_logo_diagnosis
    union all select 'fct_new_logo_diagnosis', h2_segment_months from fct_new_logo_diagnosis
    union all select 'fct_revenue_budget_bridge', amount from fct_revenue_budget_bridge
    union all select 'fct_gross_profit_bridge', amount from fct_gross_profit_bridge
    union all select 'fct_opex_budget_bridge', amount from fct_opex_budget_bridge
    union all select 'fct_operating_income_bridge', amount from fct_operating_income_bridge
    union all select 'fct_headcount_budget_bridge', amount from fct_headcount_budget_bridge where amount is not null
    union all select 'fct_cash_runway_policy', headroom_months from fct_cash_runway_policy
    union all select 'fct_cash_runway_policy', policy_runway_months from fct_cash_runway_policy
    union all select 'fct_hiring_scenario', incremental_ending_arr from fct_hiring_scenario
    union all select 'fct_hiring_scenario', incremental_cash_impact from fct_hiring_scenario
    union all select 'fct_hiring_scenario', incremental_operating_income from fct_hiring_scenario
    union all select 'fct_hiring_scenario', cumulative_hires from fct_hiring_scenario
    union all select 'fct_cash_runway_policy', board_runway_floor_months from fct_cash_runway_policy
    union all select 'fct_management_variance', variance from fct_management_variance
    union all select 'int_budget_reforecast_comparison', base_amount - budget_amount from int_budget_reforecast_comparison
    -- Subscription/Services COGS impact is payroll + non-payroll combined -- a calculated sum
    -- of two fct_gross_profit_bridge lines, still independently re-derivable from that same
    -- stored table, not a number invented for the commentary text.
    union all
    select 'fct_gross_profit_bridge', sum(case when line_item like 'Subscription COGS%' then amount else 0 end)
    from fct_gross_profit_bridge where unit = 'usd' and line_order between 3 and 6
    union all
    select 'fct_gross_profit_bridge', sum(case when line_item like 'Services COGS%' then amount else 0 end)
    from fct_gross_profit_bridge where unit = 'usd' and line_order between 3 and 6
),

commentary_traceable as (
    select 'commentary_traceable' as grain,
           cast(e.commentary_id as varchar) || ' / ' || e.evidence_label as grain_key,
           1.0 as implied_value, 0.0 as bound
    from fct_commentary_evidence e
    where not exists (
        select 1 from source_amounts_pool p
        where p.source_model = e.source_model and abs(p.amount - e.evidence_amount) < 1.0
    )
),

every_commentary_row_has_evidence as (
    select 'every_commentary_row_has_evidence' as grain, cast(c.commentary_id as varchar) as grain_key,
           count(e.commentary_id)::double as implied_value, 1.0 as bound
    from fct_commentary_output c
    left join fct_commentary_evidence e on e.commentary_id = c.commentary_id
    group by 1, 2
    having count(e.commentary_id) = 0
),

materiality_enforced as (
    -- Runway / Hiring are mandatory governance commentary (section 16's documented exception).
    -- Segment commentary uses its own materiality gate (the same $250k ARR threshold applied at
    -- segment grain, since fct_management_variance is company-level only) -- checked directly
    -- against the stored variance rather than against fct_management_variance.
    select 'materiality_enforced' as grain, cast(c.commentary_id as varchar) as grain_key, 1.0 as implied_value, 0.0 as bound
    from fct_commentary_output c
    left join fct_management_variance mv on mv.metric = c.metric
    where c.section not in ('Runway', 'Hiring', 'Segment')
      and (mv.materiality_flag is null or mv.materiality_flag = false)
    union all
    select 'materiality_enforced', cast(c.commentary_id as varchar), 1.0, 0.0
    from fct_commentary_output c
    where c.section = 'Segment' and c.materiality_score < 250000
),

priority_valid as (
    select 'priority_valid' as grain, cast(commentary_id as varchar) as grain_key, 1.0 as implied_value, 0.0 as bound
    from fct_commentary_output
    where priority not in ('Critical', 'High', 'Medium', 'Low')
),

no_duplicate_commentary_id as (
    select 'no_duplicate_commentary_id' as grain, cast(commentary_id as varchar) as grain_key,
           count(*)::double as implied_value, 1.0 as bound
    from fct_commentary_output
    group by 1, 2
    having count(*) > 1
),

polarity_consistent as (
    select 'polarity_consistent' as grain, mv.metric as grain_key, 1.0 as implied_value, 0.0 as bound
    from fct_management_variance mv
    join int_metric_polarity p on p.metric = mv.metric
    where mv.favorable_unfavorable is distinct from (
        case
            when p.polarity = 'higher_favorable' then
                case when mv.variance > 0 then 'Favorable' when mv.variance < 0 then 'Unfavorable' else 'In line' end
            when p.polarity = 'lower_favorable' then
                case when mv.variance < 0 then 'Favorable' when mv.variance > 0 then 'Unfavorable' else 'In line' end
            when p.polarity = 'contextual' then 'N/A'
        end
    )
),

top_driver_ranking_raw as (
    select headline_metric, driver, rank_abs_amount as implied_value,
           rank() over (partition by headline_metric order by abs(amount) desc) as bound
    from int_commentary_candidates
),

top_driver_ranking_correct as (
    select 'top_driver_ranking_correct' as grain, headline_metric || ' / ' || driver as grain_key,
           implied_value, bound
    from top_driver_ranking_raw
    where implied_value <> bound
),

allocated_segment_priority_capped as (
    select 'allocated_segment_priority_capped' as grain, cast(commentary_id as varchar) as grain_key,
           1.0 as implied_value, 0.0 as bound
    from fct_commentary_output
    where section = 'Segment' and priority in ('Critical', 'High')
),

all_checks as (
    select grain, grain_key, implied_value, bound from arr_bridge_reconciles
    union all select grain, grain_key, implied_value, bound from segment_arr_sums_to_company
    union all select grain, grain_key, implied_value, bound from revenue_bridge_reconciles
    union all select grain, grain_key, implied_value, bound from gross_profit_bridge_reconciles
    union all select grain, grain_key, implied_value, bound from opex_bridge_reconciles
    union all select grain, grain_key, implied_value, bound from operating_income_bridge_reconciles
    union all select grain, grain_key, implied_value, bound from headcount_bridge_consistent
    union all select grain, grain_key, implied_value, bound from no_plug_lines
    union all select grain, grain_key, implied_value, bound from commentary_traceable
    union all select grain, grain_key, implied_value, bound from every_commentary_row_has_evidence
    union all select grain, grain_key, implied_value, bound from materiality_enforced
    union all select grain, grain_key, implied_value, bound from priority_valid
    union all select grain, grain_key, implied_value, bound from no_duplicate_commentary_id
    union all select grain, grain_key, implied_value, bound from polarity_consistent
    union all select grain, grain_key, implied_value, bound from top_driver_ranking_correct
    union all select grain, grain_key, implied_value, bound from allocated_segment_priority_capped
)

select grain, grain_key, implied_value, bound
from all_checks
order by grain, grain_key
