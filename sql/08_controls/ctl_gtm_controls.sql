-- Build gate for Phase 5 (GTM capacity, pipeline, CRM-to-ARR reconciliation, unit economics).
-- Any row this query returns is a violation and the build exits non-zero. An empty result set
-- is PASS. This also fulfils PHASE1_SPEC 6.2's ctl_crm_to_arr role (check G).
--
--   A  capacity_non_negative        no rep-month has negative quota or capacity (blended or
--                                   New Logo)
--   A2 new_logo_capacity_not_greater_than_blended   New Logo productive capacity, a FRACTION of
--                                   blended capacity, can never exceed it
--   B  ramp_bounds                  0 <= ramp_pct <= 1
--   C  attainment_denominator       actual_attainment is only ever populated where the ramped
--                                   quota denominator is positive
--   D  pipeline_non_negative        no open opportunity has negative ACV
--   E  win_rate_bounds              0 <= historical New Logo win rate <= 1, by segment
--   F  crm_arr_bridge_ties          the New Logo and Expansion bridge components sum to the
--                                   landed ARR line, by construction
--   G  crm_arr_residual_tolerance   FY2025 New Logo unexplained residual < 0.5% of FY2025 New
--                                   Logo ARR (PHASE1_SPEC 8.8)
--   H  allocation_reconciles        segment cost shares sum to the cost centre's own GL total,
--                                   every cost centre and month
--   I  cac_no_divide_by_zero        no CAC value is populated for a segment/quarter with zero
--                                   new logos
--   J  sales_efficiency_denominator prior-quarter S&M is present and positive wherever Net ARR
--                                   Sales Efficiency or the Magic Number is populated
with capacity_non_negative as (
    select 'capacity_non_negative' as grain,
           rep_id || ' / ' || month_end_date::varchar as grain_key,
           least(annual_quota, theoretical_quota_capacity, expected_productive_capacity,
                 new_logo_productive_capacity) as implied_value,
           0.0 as bound
    from fct_sales_capacity
    where annual_quota < 0 or theoretical_quota_capacity < 0 or expected_productive_capacity < 0
       or new_logo_productive_capacity < 0
),

new_logo_capacity_not_greater_than_blended as (
    -- New Logo productive capacity is a FRACTION of blended capacity (new_logo_share_of_bookings
    -- is a ratio in [0, 1]); it can never exceed the blended figure it is derived from.
    select 'new_logo_capacity_not_greater_than_blended' as grain,
           rep_id || ' / ' || month_end_date::varchar as grain_key,
           new_logo_productive_capacity as implied_value,
           expected_productive_capacity as bound
    from fct_sales_capacity
    where new_logo_productive_capacity > expected_productive_capacity + 0.01
),

ramp_bounds as (
    select 'ramp_bounds' as grain,
           rep_id || ' / ' || month_end_date::varchar as grain_key,
           ramp_pct as implied_value, 1.0 as bound
    from fct_sales_capacity
    where ramp_pct < 0 - 1e-9 or ramp_pct > 1.0 + 1e-9
),

attainment_denominator as (
    select 'attainment_denominator' as grain,
           rep_id || ' / ' || month_end_date::varchar as grain_key,
           theoretical_quota_capacity as implied_value, 0.0 as bound
    from fct_sales_capacity
    where actual_attainment is not null and theoretical_quota_capacity <= 0
),

pipeline_non_negative as (
    select 'pipeline_non_negative' as grain, opportunity_id as grain_key,
           acv as implied_value, 0.0 as bound
    from fct_pipeline_snapshot
    where acv < 0
),

win_rate_bounds as (
    select 'win_rate_bounds' as grain, segment as grain_key,
           sum(case when is_won then 1.0 else 0.0 end) / nullif(count(*), 0) as implied_value,
           1.0 as bound
    from int_crm_opportunity_normalized
    where deal_type = 'New Logo' and (is_won or is_lost)
    group by segment
    having sum(case when is_won then 1.0 else 0.0 end) / nullif(count(*), 0) < 0 - 1e-9
        or sum(case when is_won then 1.0 else 0.0 end) / nullif(count(*), 0) > 1.0 + 1e-9
),

crm_arr_bridge_ties as (
    select
        'crm_arr_bridge_ties' as grain,
        period || ' / ' || bridge_type as grain_key,
        sum(case when line_item not like 'Landed%' and line_item <> 'Unexplained residual'
                 then amount else 0 end)
            + sum(case when line_item = 'Unexplained residual' then amount else 0 end) as implied_value,
        sum(case when line_item like 'Landed%' then amount else 0 end) as bound
    from fct_crm_arr_reconciliation
    where bridge_type in ('New Logo', 'Expansion')
    group by 1, 2
    having abs(
        sum(case when line_item not like 'Landed%' and line_item <> 'Unexplained residual' then amount else 0 end)
        + sum(case when line_item = 'Unexplained residual' then amount else 0 end)
        - sum(case when line_item like 'Landed%' then amount else 0 end)
    ) >= 1.00
),

crm_arr_residual_tolerance as (
    select
        'crm_arr_residual_tolerance' as grain,
        'FY2025 / New Logo' as grain_key,
        abs(r.amount) as implied_value,
        0.005 * l.amount as bound
    from fct_crm_arr_reconciliation r
    join fct_crm_arr_reconciliation l
        on l.period = r.period and l.bridge_type = 'New Logo' and l.line_item like 'Landed%'
    where r.period = 'FY2025' and r.bridge_type = 'New Logo' and r.line_item = 'Unexplained residual'
      and abs(r.amount) > 0.005 * l.amount
),

allocation_reconciles as (
    select
        'allocation_reconciles' as grain,
        month_end_date::varchar || ' / ' || cost_center as grain_key,
        sum(segment_cost_share_pct) as implied_value,
        1.0 as bound
    from int_gtm_cost_allocation
    group by 1, 2
    having abs(sum(segment_cost_share_pct) - 1.0) >= 1e-6
),

cac_no_divide_by_zero as (
    select 'cac_no_divide_by_zero' as grain,
           segment || ' / ' || fiscal_quarter as grain_key,
           new_logos_count::double as implied_value, 0.0 as bound
    from fct_unit_economics
    where new_logos_count = 0 and cac is not null
),

sales_efficiency_denominator as (
    select 'sales_efficiency_denominator' as grain, fiscal_quarter as grain_key,
           prior_quarter_sm as implied_value, 0.0 as bound
    from fct_sales_efficiency
    where (net_arr_sales_efficiency is not null or magic_number is not null)
      and (prior_quarter_sm is null or prior_quarter_sm <= 0)
),

all_checks as (
    select grain, grain_key, implied_value, bound from capacity_non_negative
    union all select grain, grain_key, implied_value, bound from new_logo_capacity_not_greater_than_blended
    union all select grain, grain_key, implied_value, bound from ramp_bounds
    union all select grain, grain_key, implied_value, bound from attainment_denominator
    union all select grain, grain_key, implied_value, bound from pipeline_non_negative
    union all select grain, grain_key, implied_value, bound from win_rate_bounds
    union all select grain, grain_key, implied_value, bound from crm_arr_bridge_ties
    union all select grain, grain_key, implied_value, bound from crm_arr_residual_tolerance
    union all select grain, grain_key, implied_value, bound from allocation_reconciles
    union all select grain, grain_key, implied_value, bound from cac_no_divide_by_zero
    union all select grain, grain_key, implied_value, bound from sales_efficiency_denominator
)

select grain, grain_key, implied_value, bound
from all_checks
order by grain, grain_key
