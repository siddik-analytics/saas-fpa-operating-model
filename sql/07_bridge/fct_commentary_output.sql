-- Deterministic management commentary. Every sentence below is assembled in SQL from calculated
-- fields in the bridge and diagnostic models above -- no LLM, no free text typed in, and no
-- hardcoded conclusion (PHASE1_SPEC-analogous governing constraint: derive, never fabricate).
-- Rules enforced structurally, not by convention:
--   "primarily"   only used when a driver's share of total absolute variance clears
--                 int_commentary_params.primary_driver_share_threshold
--   "offset"      only used for a driver opposite in sign to the headline variance AND clearing
--                 int_commentary_params.offsetting_driver_share_threshold
--   materiality   a row is generated only if fct_management_variance.materiality_flag is true,
--                 or the row is mandatory governance commentary (Runway, Hiring) -- section 16's
--                 documented exception
--   priority      centralised thresholds (int_commentary_params: high_abs_usd, high_pct), never
--                 assigned because a number is merely negative
-- Grain: one row per commentary item. `driver_1` / `driver_2` and their amounts are raw source
-- values (not formatted text), so ctl_bridge_commentary can verify every number embedded in
-- `headline` / `detail` ties back to a stored column, not to text alone.
with params as (
    select
        max(case when param = 'primary_driver_share_threshold' then value end) as primary_share,
        max(case when param = 'offsetting_driver_share_threshold' then value end) as offset_share,
        max(case when param = 'high_abs_usd' then value end) as high_abs_usd,
        max(case when param = 'high_pct' then value end) as high_pct
    from int_commentary_params
),

-- ============================================================================
-- Exit ARR
-- ============================================================================
arr_diag as (select * from fct_new_logo_diagnosis where segment = 'Total'),

arr_top as (select * from int_commentary_candidates where headline_metric = 'exit_arr' and rank_abs_amount = 1),
arr_offset as (select * from int_commentary_candidates where headline_metric = 'exit_arr' and is_material_offset limit 1),
-- The second-largest driver pushing in the SAME direction as the headline variance (i.e. a
-- second material unfavorable driver here, since Exit ARR is unfavorable) -- generic, not
-- hardcoded to Contraction: whichever same-signed driver ranks #2 and clears the ARR
-- materiality bar is surfaced. This is deliberately NOT the overall rank-2 driver (arr_offset
-- above already covers the case where the overall #2 is an opposite-signed offset instead).
arr_secondary as (
    select * from int_commentary_candidates
    where headline_metric = 'exit_arr' and is_material_secondary_same_direction
),

arr_row as (
    select
        'ARR' as section, 'exit_arr' as metric, mv.materiality_flag, mv.variance, mv.variance_pct,
        'Dec-2026 Exit ARR is ' || printf('$%.2fM', abs(mv.variance) / 1e6)
            || case when mv.variance < 0 then ' below Budget.' else ' above Budget.' end as headline,
        (case when t.share_of_total_abs_variance >= p.primary_share
              then 'The variance is primarily ' || lower(t.driver_category) || '-driven; ' || t.driver
              else 'The largest ' || case when mv.variance < 0 then 'unfavorable' else 'favorable' end || ' driver is ' || t.driver end
            || ' at ' || printf('$%.2fM', abs(t.amount) / 1e6)
            || case when t.amount < 0 then ' unfavorable to Budget.' else ' favorable to Budget.' end
            || case when sec.driver is not null
                     then ' ' || sec.driver || ' is another material ' || case when mv.variance < 0 then 'unfavorable' else 'favorable' end
                          || ' driver at ' || printf('$%.2fM', abs(sec.amount) / 1e6) || '.'
                     else '' end
            || case when o.driver is not null
                     then ' This is partly offset by ' || o.driver || ' at ' || printf('$%.2fM', abs(o.amount) / 1e6) || ' favorable.'
                     else '' end
        ) as detail,
        'Pipeline is the binding New Logo constraint in ' || cast(d.h2_pipeline_bound_months as integer)
            || ' of ' || cast(d.h2_segment_months as integer) || ' H2 2026 segment-months ('
            || d.primary_binding_constraint || '-bound overall).' as supporting_evidence,
        case when t.driver = 'New Logo ARR variance' and d.primary_binding_constraint = 'Pipeline'
             then 'Near-term ARR growth depends more on pipeline creation and conversion than on adding quota capacity.'
             else 'Monitor ' || t.driver || ' against plan through H2.' end as management_implication,
        t.driver as driver_1, t.amount as driver_1_amount,
        coalesce(sec.driver, o.driver) as driver_2, coalesce(sec.amount, o.amount) as driver_2_amount,
        'fct_arr_budget_bridge' as source_model
    from fct_management_variance mv
    cross join params p
    join arr_top t on true
    join arr_diag d on true
    left join arr_secondary sec on true
    left join arr_offset o on true
    where mv.metric = 'exit_arr'
),

-- ============================================================================
-- New Logo operating diagnosis (separate from the dollar bridge -- LEAST() interaction)
-- ============================================================================
new_logo_row as (
    select
        'ARR' as section, 'new_logo_arr' as metric, mv.materiality_flag, mv.variance, mv.variance_pct,
        'FY2026 New Logo ARR is ' || printf('$%.2fM', abs(mv.variance) / 1e6)
            || case when mv.variance < 0 then ' below Budget.' else ' above Budget.' end as headline,
        d.primary_binding_constraint || ' is the binding constraint on New Logo ARR in H2 2026 ('
            || cast(d.h2_pipeline_bound_months as integer) || ' of ' || cast(d.h2_segment_months as integer)
            || ' segment-months pipeline-bound, ' || cast(d.h2_capacity_bound_months as integer) || ' capacity-bound). '
            || 'Pipeline-supported bookings total ' || printf('$%.2fM', d.h2_pipeline_supported_arr / 1e6)
            || ' against capacity-supported bookings of ' || printf('$%.2fM', d.h2_capacity_supported_arr / 1e6)
            || ' over the same window.' as detail,
        'H2 2026 realised (constrained) New Logo ARR: ' || printf('$%.2fM', d.h2_constrained_new_logo_arr / 1e6) || '.' as supporting_evidence,
        case when d.primary_binding_constraint = 'Pipeline'
             then 'Additional sales capacity alone would not close this gap while pipeline remains the binding constraint; pipeline creation and conversion are the more relevant levers.'
             else 'Sales capacity is the binding constraint; incremental pipeline alone would not close this gap.' end as management_implication,
        'New Logo ARR variance' as driver_1, mv.variance as driver_1_amount,
        null as driver_2, null::double as driver_2_amount,
        'fct_new_logo_diagnosis' as source_model
    from fct_management_variance mv
    join fct_new_logo_diagnosis d on d.segment = 'Total'
    where mv.metric = 'new_logo_arr'
),

-- ============================================================================
-- Revenue
-- ============================================================================
rev_top as (select * from int_commentary_candidates where headline_metric = 'total_revenue' and rank_abs_amount = 1),
rev_second as (select * from int_commentary_candidates where headline_metric = 'total_revenue' and rank_abs_amount = 2),

revenue_row as (
    select
        'Revenue' as section, 'total_revenue' as metric, mv.materiality_flag, mv.variance, mv.variance_pct,
        'FY2026 Revenue is ' || printf('$%.2fM', abs(mv.variance) / 1e6)
            || case when mv.variance < 0 then ' below Budget.' else ' above Budget.' end as headline,
        (case when t.share_of_total_abs_variance >= p.primary_share
              then 'The variance is primarily driven by ' || t.driver
              else 'The largest single driver is ' || t.driver end
            || ' at ' || printf('$%.2fM', abs(t.amount) / 1e6)
            || case when t.amount < 0 then ' unfavorable to Budget.' else ' favorable to Budget.' end
        ) as detail,
        'Revenue decomposition ties to the ARR bridge: see fct_arr_budget_bridge for the underlying New Logo / Expansion / retention movements.' as supporting_evidence,
        'Revenue is a lagged function of ARR; a revenue shortfall driven by the ARR / recurring-base effect will persist into FY2027 unless the underlying ARR gap closes.' as management_implication,
        t.driver as driver_1, t.amount as driver_1_amount,
        s.driver as driver_2, s.amount as driver_2_amount,
        'fct_revenue_budget_bridge' as source_model
    from fct_management_variance mv
    cross join params p
    join rev_top t on true
    left join rev_second s on true
    where mv.metric = 'total_revenue'
),

-- ============================================================================
-- Gross Profit / Gross Margin
-- ============================================================================
gp_top as (select * from int_commentary_candidates where headline_metric = 'gross_profit' and rank_abs_amount = 1),
gp_second as (select * from int_commentary_candidates where headline_metric = 'gross_profit' and rank_abs_amount = 2),
rev_var as (select variance as revenue_variance from fct_management_variance where metric = 'total_revenue'),
margin_bps as (select variance as margin_bps_variance from fct_management_variance where metric = 'gross_margin_bps'),

-- Subscription COGS and Services COGS impact, each payroll + non-payroll combined, read
-- straight from the bridge's own lines -- the wording below is built from these two SIGNS,
-- never asserted as "lower cost of revenue" regardless of what the two components actually did.
gp_cogs_components as (
    select
        sum(case when line_item like 'Subscription COGS%' then amount else 0 end) as sub_cogs_impact,
        sum(case when line_item like 'Services COGS%' then amount else 0 end) as svc_cogs_impact
    from fct_gross_profit_bridge
    where unit = 'usd' and line_order between 3 and 6
),

gp_cogs_text as (
    select
        sub_cogs_impact, svc_cogs_impact,
        -- abs() + an explicit +/- prefix everywhere, so a negative amount never renders as the
        -- malformed "$-0.04M" that printf('$%.2fM', x) produces for a negative x.
        case
            when sub_cogs_impact >= 0 and svc_cogs_impact >= 0 then
                'Favorable Subscription COGS (+' || printf('$%.2fM', abs(sub_cogs_impact) / 1e6)
                    || ') and favorable Services COGS (+' || printf('$%.2fM', abs(svc_cogs_impact) / 1e6) || ') both contribute to the margin improvement.'
            when sub_cogs_impact < 0 and svc_cogs_impact < 0 then
                'Both Subscription COGS (-' || printf('$%.2fM', abs(sub_cogs_impact) / 1e6)
                    || ') and Services COGS (-' || printf('$%.2fM', abs(svc_cogs_impact) / 1e6) || ') ran unfavorable to Budget.'
            when sub_cogs_impact >= 0 and svc_cogs_impact < 0 then
                case when abs(sub_cogs_impact) > abs(svc_cogs_impact)
                     then 'Favorable Subscription COGS (+' || printf('$%.2fM', abs(sub_cogs_impact) / 1e6)
                          || ') more than offsets the smaller unfavorable Services COGS variance (-' || printf('$%.2fM', abs(svc_cogs_impact) / 1e6) || ').'
                     else 'Unfavorable Services COGS (-' || printf('$%.2fM', abs(svc_cogs_impact) / 1e6)
                          || ') is only partly offset by favorable Subscription COGS (+' || printf('$%.2fM', abs(sub_cogs_impact) / 1e6) || ').' end
            else
                case when abs(svc_cogs_impact) > abs(sub_cogs_impact)
                     then 'Favorable Services COGS (+' || printf('$%.2fM', abs(svc_cogs_impact) / 1e6)
                          || ') more than offsets the smaller unfavorable Subscription COGS variance (-' || printf('$%.2fM', abs(sub_cogs_impact) / 1e6) || ').'
                     else 'Unfavorable Subscription COGS (-' || printf('$%.2fM', abs(sub_cogs_impact) / 1e6)
                          || ') is only partly offset by favorable Services COGS (+' || printf('$%.2fM', abs(svc_cogs_impact) / 1e6) || ').' end
        end as cogs_sign_sentence
    from gp_cogs_components
),

gp_row as (
    select
        'Profitability' as section, 'gross_profit' as metric, mv.materiality_flag, mv.variance, mv.variance_pct,
        'FY2026 Gross Profit is ' || printf('$%.2fM', abs(mv.variance) / 1e6)
            || case when mv.variance >= 0 then ' above Budget' else ' below Budget' end
            || case when mv.variance >= 0 and rv.revenue_variance < 0 then ' despite lower Revenue.'
                     when mv.variance < 0 and rv.revenue_variance >= 0 then ' despite higher Revenue.'
                     else '.' end as headline,
        'Gross margin is ' || printf('%.0f', abs(mb.margin_bps_variance)) || ' bps '
            || case when mb.margin_bps_variance >= 0 then 'above' else 'below' end || ' Budget. '
            || ct.cogs_sign_sentence
            || case when rv.revenue_variance < 0
                     then ' Revenue itself ran ' || printf('$%.2fM', abs(rv.revenue_variance) / 1e6) || ' below Budget over the same period.'
                    when rv.revenue_variance > 0
                     then ' Revenue itself ran ' || printf('$%.2fM', rv.revenue_variance / 1e6) || ' above Budget over the same period.'
                    else '' end
        as detail,
        'COGS driver detail (payroll vs. non-payroll, by Subscription/Services) is in fct_gross_profit_bridge.' as supporting_evidence,
        case when ct.sub_cogs_impact >= 0 and ct.svc_cogs_impact >= 0
             then 'The margin improvement traces to lower cost of revenue across both Subscription and Services relative to Budget, not to a revenue mix shift.'
             when ct.sub_cogs_impact >= 0 and ct.svc_cogs_impact < 0
             then 'The margin improvement traces to lower Subscription cost of revenue, which more than offsets a smaller unfavorable Services COGS variance; it is not a revenue mix shift.'
             when ct.sub_cogs_impact < 0 and ct.svc_cogs_impact >= 0
             then 'The margin improvement traces to lower Services cost of revenue, which more than offsets a smaller unfavorable Subscription COGS variance; it is not a revenue mix shift.'
             else 'Both cost-of-revenue components ran unfavorable to Budget; review the underlying COGS driver detail before attributing the margin change to a single cause.'
        end as management_implication,
        t.driver as driver_1, t.amount as driver_1_amount,
        s.driver as driver_2, s.amount as driver_2_amount,
        'fct_gross_profit_bridge' as source_model
    from fct_management_variance mv
    cross join params p
    cross join rev_var rv
    cross join margin_bps mb
    cross join gp_cogs_text ct
    join gp_top t on true
    left join gp_second s on true
    where mv.metric = 'gross_profit'
),

-- ============================================================================
-- OpEx
-- ============================================================================
opex_top as (select * from int_commentary_candidates where headline_metric = 'total_opex' and rank_abs_amount = 1),
opex_second as (select * from int_commentary_candidates where headline_metric = 'total_opex' and rank_abs_amount = 2),

opex_row as (
    select
        'OpEx' as section, 'total_opex' as metric, mv.materiality_flag, mv.variance, mv.variance_pct,
        'FY2026 OpEx is ' || printf('$%.2fM', abs(mv.variance) / 1e6)
            || case when mv.variance > 0 then ' above Budget.' else ' below Budget.' end as headline,
        (case when t.share_of_total_abs_variance >= p.primary_share
              then 'The variance is primarily ' || t.driver
              else 'The largest single driver is ' || t.driver end)
            || ' at ' || printf('$%.2fM', abs(t.amount) / 1e6)
            || case when t.amount > 0 then ' unfavorable to Budget.' else ' favorable to Budget.' end
        as detail,
        'Category-level detail (Sales & Marketing / R&D / G&A, each split payroll / commissions / non-payroll) is in fct_opex_budget_bridge.' as supporting_evidence,
        'Cost detail is provided for review; this report does not recommend a cost reduction based on the OpEx variance alone.' as management_implication,
        t.driver as driver_1, t.amount as driver_1_amount,
        s.driver as driver_2, s.amount as driver_2_amount,
        'fct_opex_budget_bridge' as source_model
    from fct_management_variance mv
    cross join params p
    join opex_top t on true
    left join opex_second s on true
    where mv.metric = 'total_opex'
),

-- ============================================================================
-- Operating Income / Loss
-- ============================================================================
oi_top as (select * from int_commentary_candidates where headline_metric = 'operating_income' and rank_abs_amount = 1),
oi_second as (select * from int_commentary_candidates where headline_metric = 'operating_income' and rank_abs_amount = 2),

oi_row as (
    select
        'Operating Income' as section, 'operating_income' as metric, mv.materiality_flag, mv.variance, mv.variance_pct,
        'FY2026 Operating Loss is ' || printf('$%.2fM', abs(mv.variance) / 1e6)
            || case when mv.variance < 0 then ' worse than Budget.' else ' better than Budget.' end as headline,
        (case when t.share_of_total_abs_variance >= p.primary_share
              then 'The variance is primarily driven by ' || t.driver
              else 'The largest single driver is ' || t.driver end)
            || ' at ' || printf('$%.2fM', abs(t.amount) / 1e6)
            || case when t.amount < 0 then ' unfavorable to Budget.' else ' favorable to Budget.' end
        as detail,
        'Full revenue / COGS / OpEx walk is in fct_operating_income_bridge.' as supporting_evidence,
        'The operating-income variance is small relative to Revenue and OpEx individually, reflecting partially offsetting effects rather than one dominant cause.' as management_implication,
        t.driver as driver_1, t.amount as driver_1_amount,
        s.driver as driver_2, s.amount as driver_2_amount,
        'fct_operating_income_bridge' as source_model
    from fct_management_variance mv
    cross join params p
    join oi_top t on true
    left join oi_second s on true
    where mv.metric = 'operating_income'
),

-- ============================================================================
-- Headcount -- contextual polarity, no favorable/unfavorable language
-- ============================================================================
headcount_row as (
    select
        'Headcount' as section, 'ending_headcount' as metric, mv.materiality_flag, mv.variance, mv.variance_pct,
        'Dec-2026 Ending Headcount is ' || printf('%.1f', abs(mv.variance))
            || case when mv.variance >= 0 then ' FTE above Budget.' else ' FTE below Budget.' end as headline,
        'fact_budget carries Ending Headcount as a single company-level statistical figure with no functional breakdown, so this variance cannot be bridged by function against Budget; Base''s own ending headcount by function is in fct_headcount_budget_bridge.' as detail,
        'Base headcount build: existing population net-of-backfill attrition plus already-open requisitions across all functions (fill date 31-Aug-2026).' as supporting_evidence,
        'Headcount variance is not automatically favorable or unfavorable; read alongside the OpEx payroll driver detail before drawing a conclusion.' as management_implication,
        'Net headcount variance' as driver_1, mv.variance as driver_1_amount,
        null as driver_2, null::double as driver_2_amount,
        'fct_headcount_budget_bridge' as source_model
    from fct_management_variance mv
    where mv.metric = 'ending_headcount'
),

-- ============================================================================
-- Runway -- mandatory governance commentary (always generated)
-- ============================================================================
runway_facts as (
    select
        max(case when path = 'Base' then policy_runway_months end) as base_runway,
        max(case when path = 'Base' then headroom_months end) as base_headroom,
        max(case when path = 'Bear' then policy_runway_months end) as bear_runway,
        max(case when path = 'Bear' then headroom_months end) as bear_headroom,
        max(case when path = 'Bear' then breaches_floor end) as bear_breaches,
        max(case when path = 'Bull' then policy_runway_months end) as bull_runway,
        max(case when path = 'Base_FullClose' then policy_runway_months end) as fullclose_runway,
        max(case when path = 'Base_FullClose' then headroom_months end) as fullclose_headroom,
        max(board_runway_floor_months) as floor_months,
        bool_or(breaches_floor) as any_breach
    from fct_cash_runway_policy
),

-- Generic breach lead: names WHICHEVER operating scenario(s) among Bear / Base / Bull actually
-- breach the Board floor, and whichever do not -- never hardcoded to "Bear" or "Base" by name.
-- If none breach, the headline falls back to the original Base-centric framing.
runway_breach_summary as (
    select
        count(*) filter (where breaches_floor) as breach_count,
        count(*) filter (where not breaches_floor) as non_breach_count,
        string_agg(case when breaches_floor then path end, ' and '
                   order by case path when 'Bear' then 0 when 'Base' then 1 when 'Bull' then 2 end) as breaching_paths,
        string_agg(case when not breaches_floor then path end, ' and '
                   order by case path when 'Bear' then 0 when 'Base' then 1 when 'Bull' then 2 end) as non_breaching_paths
    from fct_cash_runway_policy
    where path in ('Bear', 'Base', 'Bull')
),

runway_row as (
    select
        'Runway' as section, 'policy_runway_months' as metric, true as materiality_flag,
        f.base_headroom as variance, null::double as variance_pct,
        case when rb.breach_count > 0
             then rb.breaching_paths
                 || case when rb.breach_count = 1 then ' policy runway falls' else ' policy runways fall' end
                 || ' below the ' || cast(f.floor_months as integer) || '-month Board floor, while '
                 || rb.non_breaching_paths
                 || case when rb.non_breach_count = 1 then ' remains above it.' else ' remain above it.' end
             else 'Base policy runway is ' || printf('%.1f', f.base_runway) || ' months, '
                 || printf('%.1f', f.base_headroom) || ' months of headroom above the '
                 || cast(f.floor_months as integer) || '-month Board floor.'
        end as headline,
        'Base policy runway is ' || printf('%.1f', f.base_runway) || ' months ('
            || printf('%.1f', f.base_headroom) || ' months of headroom). Bear policy runway is ' || printf('%.1f', f.bear_runway) || ' months ('
            || case when f.bear_breaches then 'breaches the floor by ' || printf('%.1f', abs(f.bear_headroom)) || ' months'
                    else printf('%.1f', f.bear_headroom) || ' months of headroom' end
            || '). Bull policy runway is ' || printf('%.1f', f.bull_runway) || ' months. '
            || 'Full Capacity-Close hiring runs at ' || printf('%.1f', f.fullclose_runway) || ' months ('
            || printf('%.1f', f.fullclose_headroom) || ' months of headroom) -- technically affordable but on materially thinner headroom than Base.' as detail,
        'fct_cash_runway_policy is a level-plus-delta sensitivity on the approved FY2027 average burn anchor, not a monthly cash-flow-statement build.' as supporting_evidence,
        case when f.bear_breaches
             then 'A Bear operating scenario would breach the Board''s 24-month runway floor on the current cost base; this is a scenario risk to monitor, not the Base-case plan.'
             else 'All modelled scenarios remain above the Board''s 24-month runway floor.' end as management_implication,
        'Base headroom' as driver_1, f.base_headroom as driver_1_amount,
        'Bear headroom' as driver_2, f.bear_headroom as driver_2_amount,
        'fct_cash_runway_policy' as source_model
    from runway_facts f
    cross join runway_breach_summary rb
),

-- ============================================================================
-- Hiring decision -- mandatory governance commentary (always generated); affordability and
-- attractiveness kept as two separate, data-derived statements (section 24)
-- ============================================================================
hiring_facts as (
    select
        max(case when path = 'Base_FullClose' then policy_runway_months end) as fullclose_runway,
        max(case when path = 'Base_FullClose' then headroom_months end) as fullclose_headroom,
        max(case when path = 'Base_FullClose' then breaches_floor end) as fullclose_breaches
    from fct_cash_runway_policy
),

hiring_scenario_facts as (
    select
        max(case when month_end_date = date '2026-12-31' then cumulative_hires end) as fullclose_hires,
        max(case when month_end_date = date '2026-12-31' then incremental_ending_arr end) as fullclose_incr_arr_2026,
        max(case when month_end_date = date '2026-12-31' then incremental_cash_impact end) as fullclose_incr_cash_2026,
        -- FY2027 fuller-ramp decision horizon (frozen Phase 6 output, unchanged): hires begin
        -- Oct-2026, so Dec-2026 is only a ramp-period snapshot; Dec-2027 is the economic view
        -- management should judge attractiveness on.
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

hiring_row as (
    select
        'Hiring' as section, 'hiring_decision' as metric, true as materiality_flag,
        s.fullclose_hires as variance, null::double as variance_pct,
        'Full Capacity-Close hiring (' || printf('%.0f', s.fullclose_hires) || ' hires) is affordable against the Board''s 24-month runway floor: '
            || printf('%.1f', f.fullclose_runway) || ' months (' || printf('%.1f', f.fullclose_headroom) || ' months of headroom). '
            || 'Targeted / Runway-Constrained hiring computes to ' || printf('%.0f', tg.targeted_hires) || ' incremental hires.' as headline,
        'On the FY2027 fuller-ramp decision horizon, Full Capacity-Close is projected to add '
            || format('${:,.0f}', s.fullclose_incr_arr_2027) || ' of incremental ARR by Dec-2027, at a cumulative incremental cash cost of '
            || format('${:,.0f}', abs(s.fullclose_incr_cash_2027)) || ' and an incremental operating income of '
            || case when s.fullclose_incr_oi_2027 < 0 then '-' else '' end || format('${:,.0f}', abs(s.fullclose_incr_oi_2027)) || ' that month ('
            || case when s.fullclose_incr_oi_2027 < 0 then 'still negative' else 'turned positive' end
            || ') -- this is the view management should use to judge economic attractiveness, not the ramp-period snapshot. '
            || 'Near-term Dec-2026 ramp impact (hires start Oct-2026, so this is a snapshot only weeks into ramp): '
            || format('${:,.0f}', s.fullclose_incr_arr_2026) || ' of incremental ARR at an incremental cash cost of '
            || format('${:,.0f}', abs(s.fullclose_incr_cash_2026)) || '.' as detail,
        d.primary_binding_constraint || ' binds New Logo ARR in ' || cast(d.h2_pipeline_bound_months as integer)
            || ' of ' || cast(d.h2_segment_months as integer) || ' H2 2026 segment-months company-wide.' as supporting_evidence,
        case when d.primary_binding_constraint = 'Pipeline'
             then 'Affordability and attractiveness are separate questions: Full Capacity-Close is affordable, but pipeline -- not capacity -- is the binding constraint on New Logo ARR, which weakens the case for incremental hiring ahead of pipeline improvement'
                  || case when s.fullclose_incr_oi_2027 < 0 then ' -- even on the fuller FY2027 ramp view, incremental operating income remains negative.' else '.' end
                  || ' Targeted hiring reflects this: it computes to hires only where forward capacity would trail pipeline, which is nowhere in the current data.'
             else 'Affordability and attractiveness are separate questions: Full Capacity-Close is affordable and capacity is the binding constraint, which supports the case for incremental hiring.' end as management_implication,
        'Full Capacity-Close incremental ARR (Dec-2027)' as driver_1, s.fullclose_incr_arr_2027 as driver_1_amount,
        'Full Capacity-Close cumulative incremental cash impact (Dec-2027)' as driver_2, s.fullclose_incr_cash_2027 as driver_2_amount,
        'fct_hiring_scenario' as source_model
    from hiring_facts f
    cross join hiring_scenario_facts s
    cross join targeted_facts tg
    cross join (select * from fct_new_logo_diagnosis where segment = 'Total') d
),

-- ============================================================================
-- Segment commentary -- most material segment ARR issue only (never one row per segment)
-- ============================================================================
segment_variance as (
    select segment, base_amount - budget_amount as variance
    from int_budget_reforecast_comparison
    where metric_group = 'arr' and metric = 'ending_arr' and segment <> 'Total'
),

segment_ranked as (
    select *, rank() over (order by abs(variance) desc) as rnk
    from segment_variance
),

segment_top_driver as (
    select c.* from int_commentary_candidates c
    join segment_ranked r on r.rnk = 1 and c.headline_metric = 'segment_arr_' || r.segment
    where c.rank_abs_amount = 1
),

segment_row as (
    -- Wording deliberately never says "below Budget" here: the segment-level Budget figure is
    -- an ALLOCATED PROXY (fact_budget carries no segment grain -- see
    -- int_budget_reforecast_comparison), not a source-grain Board-approved segment target, and
    -- the language says so explicitly rather than implying Board-approved precision it doesn't
    -- have.
    select
        'Segment' as section, 'segment_arr' as metric, true as materiality_flag,
        r.variance, null::double as variance_pct,
        r.segment || ' Exit ARR is ' || printf('$%.2fM', abs(r.variance) / 1e6)
            || case when r.variance < 0 then ' below its allocated share of the company Budget, the largest segment-level ARR gap against the allocated Budget proxy.'
                    else ' above its allocated share of the company Budget, the largest segment-level ARR movement against the allocated Budget proxy.' end as headline,
        'The largest driver within ' || r.segment || ' is ' || t.driver || ' at ' || printf('$%.2fM', abs(t.amount) / 1e6)
            || case when t.amount < 0 then ' unfavorable to the allocated Budget proxy.' else ' favorable to the allocated Budget proxy.' end as detail,
        'Segment bridge detail (Budget allocated by FY2025 mix, Base segment-native) is in fct_arr_budget_bridge.' as supporting_evidence,
        'Segment-level Budget figures are allocated from the company plan (fact_budget carries no segment grain), not an independently Board-approved segment target; read this alongside the segment-native Base figures and do not treat it with the same weight as a source-grain company variance.' as management_implication,
        t.driver as driver_1, t.amount as driver_1_amount,
        null as driver_2, null::double as driver_2_amount,
        'fct_arr_budget_bridge' as source_model
    from segment_ranked r
    join segment_top_driver t on true
    where r.rnk = 1 and abs(r.variance) >= 250000
),

all_rows as (
    select * from arr_row
    union all select * from new_logo_row
    union all select * from revenue_row
    union all select * from gp_row
    union all select * from opex_row
    union all select * from oi_row
    union all select * from headcount_row
    union all select * from runway_row
    union all select * from hiring_row
    union all select * from segment_row
),

-- ============================================================================
-- Priority -- centralised thresholds, never assigned because a number is merely negative
-- ============================================================================
with_priority as (
    -- Allocated-grain commentary (Segment) is capped at Medium regardless of its absolute
    -- dollar size: fact_budget carries no segment grain, so a segment variance is measured
    -- against an ALLOCATED proxy, not a source-grain Board-approved figure, and must never
    -- out-rank a source-grain Revenue / GP / OpEx / Operating Income variance in the Executive
    -- Summary merely because its dollar amount happens to be large.
    select r.*,
        case
            when r.section = 'Runway' and (select bool_or(breaches_floor) from fct_cash_runway_policy) then 'Critical'
            when r.section = 'Segment' then 'Medium'
            when abs(r.variance) >= p.high_abs_usd or (r.variance_pct is not null and abs(r.variance_pct) >= p.high_pct) then 'High'
            when r.section in ('Runway', 'Hiring') then 'High'
            else 'Medium'
        end as priority
    from all_rows r
    cross join params p
),

filtered as (
    -- Materiality gate: generate a row only if it is material, or it is mandatory governance
    -- commentary (Runway, Hiring -- section 16's documented exception).
    select * from with_priority
    where materiality_flag = true or section in ('Runway', 'Hiring')
)

select
    row_number() over (order by
        case priority when 'Critical' then 0 when 'High' then 1 when 'Medium' then 2 else 3 end,
        abs(variance) desc) as commentary_id,
    priority, section, metric, headline, detail, supporting_evidence, management_implication,
    driver_1, driver_1_amount, driver_2, driver_2_amount,
    abs(variance) as materiality_score, source_model
from filtered
order by commentary_id
