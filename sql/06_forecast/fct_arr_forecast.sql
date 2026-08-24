-- The forward ARR waterfall. Grain: path x segment x month, segment in ('SMB', 'Mid-Market',
-- 'Enterprise', 'Total'), path in ('Bear', 'Base', 'Bull', 'Base_Targeted', 'Base_FullClose').
-- Actuals (every dim_date.is_actual month) are read unchanged from fct_arr_waterfall and
-- replicated identically across every path -- the five paths diverge only from July 2026.
-- Forecast movements are computed independently (never as a direct guess at Ending ARR, per
-- PHASE1_SPEC-analogous section 5); Ending ARR is a running sum of Beginning ARR (the actual
-- 30 Jun 2026 company/segment ARR) plus every forecast month's net new ARR.
--
--   New Logo      LEAST(capacity, pipeline)-constrained bookings, int_gtm_capacity_pipeline_forecast
--   Expansion     a flat monthly $ run rate = expansion driver rate x the customer base's ACTUAL
--                 30 Jun 2026 ARR, held fixed rather than compounded off a growing/shrinking
--                 forecast base -- a stated simplification (docs/forecast_runway.md); the 18-month
--                 horizon and modest rates make the compounding difference second-order
--   Reactivation  a flat monthly $ run rate, scenario-invariant (int_forecast_drivers)
--   Contraction   ATR(month, segment) x contraction_share_of_atr, PLUS a flat non-ATR baseline
--   Churn         ATR(month, segment) x churn_share_of_atr, PLUS a flat non-ATR baseline
--
-- Renewal seasonality is real here because ATR(month, segment) is fct_renewal_base's own forward
-- book -- Q1/Q4-heavy, never spread evenly (PHASE1_SPEC-analogous section 13). Known limitation:
-- fct_renewal_base carries only each contract's OWN NEXT renewal date, so a contract whose
-- renewal falls early in the forecast horizon does not generate a second, later renewal event
-- inside this same 18-month window -- see docs/forecast_runway.md.
with paths as (
    select 'Bear' as path union all select 'Base' union all select 'Bull'
    union all select 'Base_Targeted' union all select 'Base_FullClose'
),

forecast_months as (
    select month_end_date from dim_date where is_forecast and month_end_date <= date '2027-12-31'
),

opening_segment_arr as (
    -- 30 Jun 2026 company/segment ARR -- the shared opening balance every path starts from.
    select segment, ending_arr from fct_arr_waterfall where month_end_date = date '2026-06-30'
),

atr_by_month_segment as (
    select renewal_month as month_end_date, segment, sum(atr_arr) as atr_arr
    from fct_renewal_base
    group by 1, 2
),

expansion_rate as (
    select scenario, segment, value as monthly_rate from int_forecast_drivers
    where driver_category = 'expansion' and driver_name = 'monthly_rate_of_beginning_arr'
),

reactivation_flat as (
    select segment, value as monthly_arr from int_forecast_drivers
    where driver_category = 'reactivation' and driver_name = 'monthly_arr'
),

churn_share as (
    select scenario, segment, value from int_forecast_drivers
    where driver_category = 'retention' and driver_name = 'churn_share_of_atr'
),

contraction_share as (
    select scenario, segment, value from int_forecast_drivers
    where driver_category = 'retention' and driver_name = 'contraction_share_of_atr'
),

baseline_churn as (
    select scenario, segment, value from int_forecast_drivers
    where driver_category = 'retention' and driver_name = 'baseline_nonatr_churn_monthly'
),

baseline_contraction as (
    select scenario, segment, value from int_forecast_drivers
    where driver_category = 'retention' and driver_name = 'baseline_nonatr_contraction_monthly'
),

new_logo_by_path as (
    select path, segment, month_end_date, constrained_new_logo_arr as new_logo_arr
    from int_gtm_capacity_pipeline_forecast
),

path_scenario as (
    select 'Bear' as path, 'Bear' as scenario
    union all select 'Base', 'Base'
    union all select 'Bull', 'Bull'
    union all select 'Base_Targeted', 'Base'
    union all select 'Base_FullClose', 'Base'
),

-- ============================================================================
-- Forecast movements, by real segment (SMB / Mid-Market / Enterprise) only --
-- Total is rolled up after the running-sum step below.
-- ============================================================================
segments as (
    select 'SMB' as segment union all select 'Mid-Market' union all select 'Enterprise'
),

forecast_movements as (
    select
        ps.path, s.segment, fm.month_end_date,
        coalesce(nl.new_logo_arr, 0) as new_logo_arr,
        coalesce(er.monthly_rate, 0) * oa.ending_arr as expansion_arr,
        coalesce(rf.monthly_arr, 0) as reactivation_arr,
        -1 * (coalesce(atr.atr_arr, 0) * coalesce(cs.value, 0) + coalesce(bc.value, 0)) as contraction_arr,
        -1 * (coalesce(atr.atr_arr, 0) * coalesce(chs.value, 0) + coalesce(bch.value, 0)) as churn_arr
    from path_scenario ps
    cross join segments s
    cross join forecast_months fm
    join opening_segment_arr oa on oa.segment = s.segment
    left join new_logo_by_path nl on nl.path = ps.path and nl.segment = s.segment and nl.month_end_date = fm.month_end_date
    left join expansion_rate er on er.scenario = ps.scenario and er.segment = s.segment
    left join reactivation_flat rf on rf.segment = s.segment
    left join atr_by_month_segment atr on atr.segment = s.segment and atr.month_end_date = fm.month_end_date
    left join contraction_share cs on cs.scenario = ps.scenario and cs.segment = s.segment
    left join churn_share chs on chs.scenario = ps.scenario and chs.segment = s.segment
    left join baseline_contraction bc on bc.scenario = ps.scenario and bc.segment = s.segment
    left join baseline_churn bch on bch.scenario = ps.scenario and bch.segment = s.segment
),

forecast_with_net as (
    select *, new_logo_arr + expansion_arr + reactivation_arr + contraction_arr + churn_arr as net_new_arr
    from forecast_movements
),

forecast_rolled as (
    select
        fwn.path, fwn.segment, fwn.month_end_date, fwn.new_logo_arr, fwn.expansion_arr,
        fwn.reactivation_arr, fwn.contraction_arr, fwn.churn_arr, fwn.net_new_arr,
        oa.ending_arr + sum(fwn.net_new_arr) over (
            partition by fwn.path, fwn.segment order by fwn.month_end_date
            rows between unbounded preceding and current row
        ) as ending_arr
    from forecast_with_net fwn
    join opening_segment_arr oa on oa.segment = fwn.segment
),

forecast_final as (
    select
        path, segment, month_end_date,
        ending_arr - net_new_arr as beginning_arr,
        new_logo_arr, expansion_arr, reactivation_arr, contraction_arr, churn_arr, ending_arr,
        false as is_actual
    from forecast_rolled
),

-- ============================================================================
-- Actuals, replicated identically across every path
-- ============================================================================
actual_segment_rows as (
    select p.path, w.segment, w.month_end_date, w.beginning_arr, w.new_logo_arr, w.expansion_arr,
           w.reactivation_arr, w.contraction_arr, w.churn_arr, w.ending_arr, true as is_actual
    from fct_arr_waterfall w
    join dim_date d on d.month_end_date = w.month_end_date
    cross join paths p
    where d.is_actual and w.segment <> 'Total'
),

segment_rows as (
    select * from actual_segment_rows
    union all
    select * from forecast_final
),

total_rows as (
    select
        path, 'Total' as segment, month_end_date,
        sum(beginning_arr) as beginning_arr, sum(new_logo_arr) as new_logo_arr,
        sum(expansion_arr) as expansion_arr, sum(reactivation_arr) as reactivation_arr,
        sum(contraction_arr) as contraction_arr, sum(churn_arr) as churn_arr,
        sum(ending_arr) as ending_arr, bool_and(is_actual) as is_actual
    from segment_rows
    group by 1, 3
),

combined as (
    select * from segment_rows
    union all
    select * from total_rows
)

select
    path, segment, month_end_date, beginning_arr, new_logo_arr, expansion_arr, reactivation_arr,
    contraction_arr, churn_arr, ending_arr, is_actual,
    case
        when is_actual then 'Actual'
        when month_end_date <= date '2026-12-31' then 'FY2026 Reforecast'
        else 'Forward Runway Projection'
    end as period_label
from combined
order by path, segment, month_end_date
