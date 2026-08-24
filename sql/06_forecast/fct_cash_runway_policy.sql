-- Board runway / policy view. Grain: one row per path (Bear, Base, Bull, Base_Targeted,
-- Base_FullClose).
--
-- fct_cash_runway (the "model-derived operating cash proxy") is deliberately NOT a full
-- cash-flow forecast -- it has no working-capital build, no capex, and no cash-flow-statement
-- adjustments beyond one D&A add-back (docs/forecast_runway.md section 8). It is useful for
-- RELATIVE comparisons -- scenario deltas, hiring deltas, monthly operating direction -- and is
-- kept completely unchanged here. It is NOT, on its own, a governance-grade answer to "is 24
-- months of runway affordable."
--
-- PHASE1_SPEC 2.3's own approved forward-burn planning assumption
-- (config anchors.cash_2026_06.forecast_fy2027_avg_monthly_net_burn, $850k/month) supplies the
-- LEVEL instead. Every path's policy burn is that same approved level, adjusted ONLY by the
-- model-derived DELTA vs Base over the same forward 12-month window (Jul-2026 to Jun-2027) --
-- never a level taken from the model itself:
--
--   Base policy burn        = approved FY2027 average monthly burn (the anchor, unchanged)
--   Scenario policy burn    = Base policy burn
--                             + (scenario's own model-derived avg burn - Base's model-derived avg burn)
--   Hiring-case policy burn = Base policy burn
--                             + (case's own model-derived avg burn - Base's model-derived avg burn)
--
-- Because "Base_Targeted" and "Base_FullClose" already carry the incremental hiring-case cash
-- impact inside fct_cash_runway (they are Base's own cash path plus that case's incremental
-- payroll cost, nothing else), and "No Incremental GTM Hiring" is Base itself, this single
-- formula covers Bear/Base/Bull and all three hiring cases without a separate code path.
with window_burn as (
    select path, avg(monthly_burn) as avg_model_burn
    from fct_cash_runway
    where month_end_date between date '2026-07-31' and date '2027-06-30'
    group by 1
),

base_model_burn as (
    select avg_model_burn from window_burn where path = 'Base'
),

policy_inputs as (
    select
        max(case when driver = 'approved_fy2027_avg_monthly_burn' then value end) as approved_base_burn,
        max(case when driver = 'board_runway_floor_months' then value end) as board_runway_floor_months,
        max(case when driver = 'opening_cash_jun_2026' then value end) as opening_cash
    from stg_forecast_assumptions
    where category = 'cash_policy'
)

select
    w.path,
    w.avg_model_burn as model_derived_avg_burn,
    b.avg_model_burn as model_derived_base_avg_burn,
    w.avg_model_burn - b.avg_model_burn as model_derived_delta_vs_base,
    pi.approved_base_burn,
    pi.approved_base_burn + (w.avg_model_burn - b.avg_model_burn) as policy_avg_monthly_burn,
    pi.opening_cash,
    pi.opening_cash / nullif(pi.approved_base_burn + (w.avg_model_burn - b.avg_model_burn), 0)
        as policy_runway_months,
    (pi.opening_cash / nullif(pi.approved_base_burn + (w.avg_model_burn - b.avg_model_burn), 0))
        - pi.board_runway_floor_months as headroom_months,
    pi.board_runway_floor_months,
    pi.opening_cash / pi.board_runway_floor_months as max_supportable_avg_monthly_burn_at_floor,
    case
        when (pi.opening_cash / nullif(pi.approved_base_burn + (w.avg_model_burn - b.avg_model_burn), 0))
             < pi.board_runway_floor_months
        then true else false
    end as breaches_floor
from window_burn w
cross join base_model_burn b
cross join policy_inputs pi
order by w.path
