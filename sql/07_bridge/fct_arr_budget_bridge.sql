-- Dec-2026 Exit ARR: Board Budget -> Independent Base Reforecast, by segment (SMB / Mid-Market
-- / Enterprise / Total). Grain: segment x line_order.
--
-- Because Beginning ARR (31-Dec-2025) is identical on both sides -- real, shared actual history,
-- not a Budget assumption -- the bridge collapses to Budget Exit ARR plus the five movement
-- variances, and reconciles to Base Exit ARR exactly:
--
--   Budget Exit ARR
--   + Opening ARR variance          (always 0.00 -- both sides start from the same 31-Dec-2025 close)
--   + New Logo ARR variance
--   + Expansion ARR variance
--   + Reactivation ARR variance
--   + Contraction ARR variance
--   + Churn ARR variance
--   = Base Reforecast Exit ARR
--
-- Segment rows: Budget's five movement components are ALLOCATED (int_budget_reforecast_
-- comparison's documented methodology); Base's are segment-native. Total is fully source on
-- both sides. `residual` is the running balance after all seven addends minus the actual Base
-- Exit ARR -- ctl_bridge_commentary's "no plug" check requires this to be zero (tolerance $1)
-- for every segment.
with pivoted as (
    select
        segment,
        max(case when metric = 'beginning_arr' then budget_amount end) as budget_beginning,
        max(case when metric = 'beginning_arr' then base_amount end) as base_beginning,
        max(case when metric = 'new_logo_arr' then budget_amount end) as budget_new_logo,
        max(case when metric = 'new_logo_arr' then base_amount end) as base_new_logo,
        max(case when metric = 'expansion_arr' then budget_amount end) as budget_expansion,
        max(case when metric = 'expansion_arr' then base_amount end) as base_expansion,
        max(case when metric = 'reactivation_arr' then budget_amount end) as budget_reactivation,
        max(case when metric = 'reactivation_arr' then base_amount end) as base_reactivation,
        max(case when metric = 'contraction_arr' then budget_amount end) as budget_contraction,
        max(case when metric = 'contraction_arr' then base_amount end) as base_contraction,
        max(case when metric = 'churn_arr' then budget_amount end) as budget_churn,
        max(case when metric = 'churn_arr' then base_amount end) as base_churn,
        max(case when metric = 'ending_arr' then budget_amount end) as budget_ending,
        max(case when metric = 'ending_arr' then base_amount end) as base_ending,
        max(case when metric = 'new_logo_arr' then budget_grain end) as movement_budget_grain
    from int_budget_reforecast_comparison
    where metric_group = 'arr'
    group by 1
),

raw_lines as (
    select segment, 1 as line_order, 'Budget Exit ARR' as line_item, 'anchor' as driver_category,
           budget_ending as amount, movement_budget_grain as budget_grain
    from pivoted
    union all
    select segment, 2, 'Opening ARR variance (31-Dec-2025 actual, identical both sides)', 'opening_arr',
           base_beginning - budget_beginning, 'source'
    from pivoted
    union all
    select segment, 3, 'New Logo ARR variance', 'new_logo', base_new_logo - budget_new_logo, movement_budget_grain
    from pivoted
    union all
    select segment, 4, 'Expansion ARR variance', 'expansion', base_expansion - budget_expansion, movement_budget_grain
    from pivoted
    union all
    select segment, 5, 'Reactivation ARR variance', 'reactivation', base_reactivation - budget_reactivation, movement_budget_grain
    from pivoted
    union all
    select segment, 6, 'Contraction ARR variance', 'contraction', base_contraction - budget_contraction, movement_budget_grain
    from pivoted
    union all
    select segment, 7, 'Churn ARR variance', 'churn', base_churn - budget_churn, movement_budget_grain
    from pivoted
),

with_running as (
    select *,
        sum(amount) over (partition by segment order by line_order rows between unbounded preceding and current row)
            as running_balance
    from raw_lines
),

residuals as (
    select segment, max(case when line_order = 7 then running_balance end) - max(p.base_ending) as residual
    from with_running w
    join pivoted p using (segment)
    group by 1
),

final_line as (
    select p.segment, 8 as line_order, 'Base Reforecast Exit ARR' as line_item, 'anchor' as driver_category,
           p.base_ending as amount, p.base_ending as running_balance, p.movement_budget_grain as budget_grain
    from pivoted p
)

select w.segment, w.line_order, w.line_item, w.driver_category, w.amount, w.running_balance,
       w.budget_grain, r.residual
from with_running w
join residuals r using (segment)
union all
select f.segment, f.line_order, f.line_item, f.driver_category, f.amount, f.running_balance,
       f.budget_grain, r.residual
from final_line f
join residuals r using (segment)
order by segment, line_order
