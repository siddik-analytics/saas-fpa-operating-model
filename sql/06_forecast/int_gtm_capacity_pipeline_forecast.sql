-- The GTM constraint, forward. Grain: path x segment x forecast month (Jul-2026 to Dec-2027).
-- `path` is five values: Bear / Base / Bull (the three operating scenarios, no incremental
-- hiring beyond already-open sales requisitions) and Base_Targeted / Base_FullClose (the two
-- management-action hiring cases, layered onto BASE operating conditions only -- PHASE1_SPEC-
-- analogous section 18's separation of operating environment from management action).
--
-- Two independently derived monthly figures, never conflated:
--   new_logo_capacity            productive New-Logo-selling capacity (quota x ramp x
--                                 attainment x New-Logo booking mix), existing reps + already-
--                                 open sales reqs + (Targeted/FullClose only) incremental hires
--   pipeline_supported_bookings  expected New Logo bookings the CRM funnel can actually produce
--                                 that month -- the current open pipeline snapshot, respecting
--                                 its own expected-close timing, PLUS a separate, explicit
--                                 forward pipeline-CREATION driver (int_forecast_drivers) for
--                                 months beyond what the snapshot already contains, win-rate-
--                                 converted and lagged by segment sales cycle
-- constrained_new_logo_arr = LEAST(new_logo_capacity, pipeline_supported_bookings) -- New Logo
-- ARR is never forecast as more than either side supports (docs/forecast_runway.md).
--
-- Incremental hire COUNTS (Targeted / Full-Capacity-Close) are computed here, from the H2 2026
-- New Logo capacity gap by segment, exactly as PHASE1_SPEC-analogous section 32 requires --
-- never typed into config. Full-Capacity-Close hires in every segment with a positive gap.
-- Targeted hires ONLY in a segment where CAPACITY, not pipeline, is the binding constraint over
-- the following 12 months (Jul-2026 to Jun-2027) -- hiring into a segment pipeline already
-- can't feed would buy capacity with no ARR behind it (section 34).
with forecast_months as (
    select month_end_date from dim_date where is_forecast and month_end_date <= date '2027-12-31'
),

month_seq as (
    select month_end_date, row_number() over (order by month_end_date) as rn from dim_date
),

segments as (
    select 'SMB' as segment union all select 'Mid-Market' union all select 'Enterprise'
),

path_scenario as (
    select 'Bear' as path, 'Bear' as scenario
    union all select 'Base', 'Base'
    union all select 'Bull', 'Bull'
    union all select 'Base_Targeted', 'Base'
    union all select 'Base_FullClose', 'Base'
),

quota_by_segment as (
    -- sales_reps.annual_quota (config/assumptions.yml), binding, same as int_rep_month.sql
    select 'SMB' as segment, 700000.0 as annual_quota, 'standard' as ramp_profile_id
    union all select 'Mid-Market', 1000000.0, 'standard'
    union all select 'Enterprise', 1400000.0, 'enterprise'
),

attrition_hazard as (
    -- Binding Phase 1 policy rate (sales_reps.annual_attrition = 0.26), applied uniformly across
    -- AE segments -- no segment-specific AE attrition rate exists in the source data
    -- (docs/forecast_runway.md, attrition treatment). Converted to a monthly hazard.
    --
    -- Deliberately the GROSS rate, unlike fct_headcount_forecast's net-of-backfill hazard: a
    -- backfilled AE has to ramp from month one, so crediting existing-rep capacity as if ordinary
    -- backfill hiring kept it flat would overstate New Logo productive capacity. This makes the
    -- capacity forecast for Sales more conservative than the headcount/payroll forecast for the
    -- same function -- a stated, deliberate asymmetry, not an inconsistency (docs/forecast_runway.md).
    select 1 - power(1 - 0.26, 1.0 / 12.0) as monthly_hazard
),

-- ============================================================================
-- Existing reps: continue ramp past 30 Jun 2026, apply expected (fractional)
-- attrition survival -- not a random departure draw, a deterministic
-- forecast expects fractional headcount, the same convention fact_forecast
-- itself uses for its own benchmark Ending Headcount line.
-- ============================================================================
existing_reps as (
    select rep_id, segment, hire_date, annual_quota, ramp_profile_id
    from dim_sales_rep
    where termination_date is null or termination_date >= date '2026-06-30'
),

existing_rep_months as (
    select
        r.rep_id, r.segment, r.annual_quota, r.ramp_profile_id, fm.month_end_date,
        date_diff('month', date_trunc('month', r.hire_date), date_trunc('month', fm.month_end_date)) + 1
            as months_since_hire,
        date_diff('month', date '2026-06-30', fm.month_end_date) as months_since_report
    from existing_reps r
    cross join forecast_months fm
),

existing_rep_capacity as (
    select
        rep_id, segment, month_end_date,
        annual_quota / 12.0 as monthly_quota,
        case
            when ramp_profile_id = 'enterprise' then
                case when months_since_hire <= 1 then 0.00 when months_since_hire = 2 then 0.15
                     when months_since_hire = 3 then 0.35 when months_since_hire = 4 then 0.60
                     when months_since_hire = 5 then 0.85 else 1.00 end
            else
                case when months_since_hire <= 1 then 0.00 when months_since_hire = 2 then 0.25
                     when months_since_hire = 3 then 0.50 when months_since_hire = 4 then 0.75
                     else 1.00 end
        end as ramp_pct,
        power(1 - ah.monthly_hazard, months_since_report) as survival_pct
    from existing_rep_months, attrition_hazard ah
),

existing_theoretical as (
    select segment, month_end_date, sum(monthly_quota * ramp_pct * survival_pct) as theoretical_capacity
    from existing_rep_capacity
    group by 1, 2
),

-- ============================================================================
-- Already-open sales requisitions: known hiring intent, not hypothetical.
-- Assumed to fill on a single date, config: forecast.open_req_assumed_fill_date
-- (2026-08-31), scenario-invariant -- see docs/forecast_runway.md.
-- ============================================================================
open_reqs as (
    select req_id,
           case department
               when 'Sales - SMB' then 'SMB'
               when 'Sales - Mid-Market' then 'Mid-Market'
               when 'Sales - Enterprise' then 'Enterprise'
           end as segment
    from stg_fact_requisition
    where status = 'Open' and function = 'Sales'
      and department in ('Sales - SMB', 'Sales - Mid-Market', 'Sales - Enterprise')
),

open_req_months as (
    select
        o.req_id, o.segment, fm.month_end_date,
        date_diff('month', date '2026-08-31', fm.month_end_date) + 1 as months_since_hire
    from open_reqs o
    cross join forecast_months fm
    where fm.month_end_date >= date '2026-08-31'
),

open_req_capacity as (
    select
        orm.req_id, orm.segment, orm.month_end_date,
        q.annual_quota / 12.0 as monthly_quota,
        case
            when q.ramp_profile_id = 'enterprise' then
                case when orm.months_since_hire <= 1 then 0.00 when orm.months_since_hire = 2 then 0.15
                     when orm.months_since_hire = 3 then 0.35 when orm.months_since_hire = 4 then 0.60
                     when orm.months_since_hire = 5 then 0.85 else 1.00 end
            else
                case when orm.months_since_hire <= 1 then 0.00 when orm.months_since_hire = 2 then 0.25
                     when orm.months_since_hire = 3 then 0.50 when orm.months_since_hire = 4 then 0.75
                     else 1.00 end
        end as ramp_pct
    from open_req_months orm
    join quota_by_segment q on q.segment = orm.segment
),

open_req_theoretical as (
    select segment, month_end_date, sum(monthly_quota * ramp_pct) as theoretical_capacity
    from open_req_capacity
    group by 1, 2
),

base_theoretical_capacity as (
    select segment, month_end_date, sum(theoretical_capacity) as theoretical_capacity
    from (
        select segment, month_end_date, theoretical_capacity from existing_theoretical
        union all
        select segment, month_end_date, theoretical_capacity from open_req_theoretical
    )
    group by 1, 2
),

expected_attainment as (
    select segment, max(expected_attainment) as expected_attainment
    from fct_sales_capacity
    where month_end_date = (select max(month_end_date) from dim_date where is_actual)
    group by 1
),

attainment_mult as (
    select scenario, value from int_forecast_drivers
    where driver_category = 'new_logo' and driver_name = 'attainment_multiplier'
),

new_logo_mix as (
    select segment, new_logo_share_of_bookings from int_gtm_new_logo_mix
),

capacity_by_path_operating as (
    -- Bear / Base / Bull -- no incremental hiring, only the attainment multiplier varies.
    select
        ps.path, btc.segment, btc.month_end_date,
        btc.theoretical_capacity,
        btc.theoretical_capacity * ea.expected_attainment * am.value as blended_capacity,
        btc.theoretical_capacity * ea.expected_attainment * am.value * nlm.new_logo_share_of_bookings
            as new_logo_capacity
    from base_theoretical_capacity btc
    cross join path_scenario ps
    join expected_attainment ea on ea.segment = btc.segment
    join attainment_mult am on am.scenario = ps.scenario
    join new_logo_mix nlm on nlm.segment = btc.segment
    where ps.path in ('Bear', 'Base', 'Bull')
),

-- ============================================================================
-- Pipeline side: current CRM snapshot (real close months, already respected
-- by fct_pipeline_snapshot) + an explicit forward pipeline-CREATION driver
-- for months the snapshot does not cover (nothing exists past 2026-10-31 in
-- the current snapshot -- Q4 2026 pipeline is genuinely thin, not
-- manufactured here). Both sides win-rate-converted to expected bookings.
-- ============================================================================
win_rate_by_path as (
    select scenario, segment, value as win_rate from int_forecast_drivers
    where driver_category = 'new_logo' and driver_name = 'win_rate'
),

existing_pipeline_bookings as (
    select
        ps.path, p.segment, p.expected_close_month as month_end_date,
        sum(p.acv) * wr.win_rate as booked_acv
    from fct_pipeline_snapshot p
    cross join path_scenario ps
    join win_rate_by_path wr on wr.scenario = ps.scenario and wr.segment = p.segment
    where p.deal_type = 'New Logo' and ps.path in ('Bear', 'Base', 'Bull')
    group by 1, 2, 3, wr.win_rate
),

pipeline_creation_by_path as (
    select scenario, segment, value as monthly_creation_acv from int_forecast_drivers
    where driver_category = 'pipeline' and driver_name = 'creation_monthly_acv'
),

pipeline_lag_by_segment as (
    select segment, cast(value as integer) as lag_months from int_forecast_drivers
    where driver_category = 'pipeline' and driver_name = 'creation_to_close_lag_months'
),

future_pipeline_bookings as (
    -- Every forecast month is a creation month; its bookings land `lag_months` later, found by
    -- the same row-sequence join docs/retention_renewals.md uses for the M-12 cohort -- robust to
    -- month-length differences, unlike interval arithmetic on a month-end date.
    select
        ps.path, s.segment, ms_close.month_end_date,
        pc.monthly_creation_acv * wr.win_rate as booked_acv
    from forecast_months fm
    cross join segments s
    cross join path_scenario ps
    join month_seq ms_c on ms_c.month_end_date = fm.month_end_date
    join pipeline_lag_by_segment l on l.segment = s.segment
    join month_seq ms_close on ms_close.rn = ms_c.rn + l.lag_months
    join pipeline_creation_by_path pc on pc.scenario = ps.scenario and pc.segment = s.segment
    join win_rate_by_path wr on wr.scenario = ps.scenario and wr.segment = s.segment
    where ms_close.month_end_date > date '2026-10-31'   -- the snapshot already covers everything through here
      and ps.path in ('Bear', 'Base', 'Bull')
),

pipeline_supported_operating as (
    select path, segment, month_end_date, sum(booked_acv) as pipeline_supported_bookings
    from (
        select * from existing_pipeline_bookings
        union all
        select * from future_pipeline_bookings
    )
    group by 1, 2, 3
),

-- ============================================================================
-- H2 2026 New Logo capacity gap by segment (Base path) -- the basis for both
-- hiring cases' hire counts, extending Phase 5's own company-blended gap
-- formula (reports/gtm_validation_report.md section 9) to segment grain.
-- ============================================================================
h2_target_company as (
    select sum(budget_amount) as company_h2_target
    from stg_fact_budget
    where version = 'FY2026-Board-Approved' and account_code = 9010
      and month_end_date between date '2026-07-31' and date '2026-12-31'
),

new_logo_mix_full as (
    select segment, share_of_company_new_logo_arr from int_gtm_new_logo_mix
),

h2_target_by_segment as (
    select nlm.segment, nlm.share_of_company_new_logo_arr * h2.company_h2_target as segment_h2_target
    from new_logo_mix_full nlm cross join h2_target_company h2
),

h2_existing_new_logo_capacity as (
    select segment, sum(new_logo_capacity) as segment_h2_existing_capacity
    from capacity_by_path_operating
    where path = 'Base' and month_end_date between date '2026-07-31' and date '2026-12-31'
    group by 1
),

avg_fully_ramped_new_logo_capacity as (
    select q.segment,
           (q.annual_quota / 12.0) * ea.expected_attainment * nlm.new_logo_share_of_bookings as monthly_capacity
    from quota_by_segment q
    join expected_attainment ea on ea.segment = q.segment
    join new_logo_mix nlm on nlm.segment = q.segment
),

twelve_month_capacity as (
    select segment, sum(new_logo_capacity) as capacity_12mo
    from capacity_by_path_operating
    where path = 'Base' and month_end_date between date '2026-07-31' and date '2027-06-30'
    group by 1
),

twelve_month_pipeline as (
    select segment, sum(pipeline_supported_bookings) as pipeline_12mo
    from pipeline_supported_operating
    where path = 'Base' and month_end_date between date '2026-07-31' and date '2027-06-30'
    group by 1
),

segment_gap as (
    select
        t.segment,
        t.segment_h2_target,
        e.segment_h2_existing_capacity,
        ceil(greatest(0, t.segment_h2_target - e.segment_h2_existing_capacity)
             / nullif(a.monthly_capacity * 6, 0)) as full_close_hires,
        case when tc.capacity_12mo < tp.pipeline_12mo then
            ceil(greatest(0, t.segment_h2_target - e.segment_h2_existing_capacity)
                 / nullif(a.monthly_capacity * 6, 0))
        else 0 end as targeted_hires,
        tc.capacity_12mo, tp.pipeline_12mo
    from h2_target_by_segment t
    join h2_existing_new_logo_capacity e on e.segment = t.segment
    join avg_fully_ramped_new_logo_capacity a on a.segment = t.segment
    join twelve_month_capacity tc on tc.segment = t.segment
    join twelve_month_pipeline tp on tp.segment = t.segment
),

-- ============================================================================
-- Incremental hire cohorts (Targeted / Full-Capacity-Close), starting
-- config: forecast.incremental_hire_start_month (2026-10-31, one month after
-- the Board decision).
-- ============================================================================
incremental_hire_months as (
    select 'Base_FullClose' as path, sg.segment, sg.full_close_hires as hires, fm.month_end_date,
           date_diff('month', date '2026-10-31', fm.month_end_date) + 1 as months_since_hire
    from segment_gap sg cross join forecast_months fm
    where fm.month_end_date >= date '2026-10-31' and sg.full_close_hires > 0
    union all
    select 'Base_Targeted', sg.segment, sg.targeted_hires, fm.month_end_date,
           date_diff('month', date '2026-10-31', fm.month_end_date) + 1
    from segment_gap sg cross join forecast_months fm
    where fm.month_end_date >= date '2026-10-31' and sg.targeted_hires > 0
),

incremental_capacity as (
    select
        ihm.path, ihm.segment, ihm.month_end_date, ihm.hires,
        q.annual_quota / 12.0 * ihm.hires *
        case
            when q.ramp_profile_id = 'enterprise' then
                case when ihm.months_since_hire <= 1 then 0.00 when ihm.months_since_hire = 2 then 0.15
                     when ihm.months_since_hire = 3 then 0.35 when ihm.months_since_hire = 4 then 0.60
                     when ihm.months_since_hire = 5 then 0.85 else 1.00 end
            else
                case when ihm.months_since_hire <= 1 then 0.00 when ihm.months_since_hire = 2 then 0.25
                     when ihm.months_since_hire = 3 then 0.50 when ihm.months_since_hire = 4 then 0.75
                     else 1.00 end
        end as incremental_theoretical_capacity
    from incremental_hire_months ihm
    join quota_by_segment q on q.segment = ihm.segment
),

incremental_capacity_priced as (
    select
        ic.path, ic.segment, ic.month_end_date, ic.hires,
        ic.incremental_theoretical_capacity,
        ic.incremental_theoretical_capacity * ea.expected_attainment as incremental_blended_capacity,
        ic.incremental_theoretical_capacity * ea.expected_attainment * nlm.new_logo_share_of_bookings
            as incremental_new_logo_capacity
    from incremental_capacity ic
    join expected_attainment ea on ea.segment = ic.segment
    join new_logo_mix nlm on nlm.segment = ic.segment
),

capacity_by_path_hiring as (
    -- Base_Targeted / Base_FullClose = Base capacity + the incremental cohort, every segment x
    -- month, even where a segment's own gap was zero (incremental_* then simply adds zero).
    select
        bpo.path, bpo.segment, bpo.month_end_date,
        bpo.theoretical_capacity + coalesce(pc.incremental_theoretical_capacity, 0) as theoretical_capacity,
        bpo.blended_capacity + coalesce(pc.incremental_blended_capacity, 0) as blended_capacity,
        bpo.new_logo_capacity + coalesce(pc.incremental_new_logo_capacity, 0) as new_logo_capacity
    from (select 'Base_Targeted' as path, segment, month_end_date, theoretical_capacity, blended_capacity, new_logo_capacity
          from capacity_by_path_operating where path = 'Base'
          union all
          select 'Base_FullClose', segment, month_end_date, theoretical_capacity, blended_capacity, new_logo_capacity
          from capacity_by_path_operating where path = 'Base') bpo
    left join incremental_capacity_priced pc
        on pc.path = bpo.path and pc.segment = bpo.segment and pc.month_end_date = bpo.month_end_date
),

pipeline_supported_hiring as (
    -- Pipeline is a demand-side constraint, independent of who is selling into it -- the hiring
    -- cases reuse the SAME Base pipeline path, never their own inflated figure.
    select 'Base_Targeted' as path, segment, month_end_date, pipeline_supported_bookings
    from pipeline_supported_operating where path = 'Base'
    union all
    select 'Base_FullClose', segment, month_end_date, pipeline_supported_bookings
    from pipeline_supported_operating where path = 'Base'
),

capacity_all as (
    select * from capacity_by_path_operating
    union all
    select * from capacity_by_path_hiring
),

pipeline_all as (
    select * from pipeline_supported_operating
    union all
    select * from pipeline_supported_hiring
),

hires_by_path as (
    select 'Base_Targeted' as path, segment, targeted_hires as incremental_hires from segment_gap
    union all
    select 'Base_FullClose', segment, full_close_hires from segment_gap
    union all
    select path, segment, 0 as incremental_hires from path_scenario cross join segments
        where path in ('Bear', 'Base', 'Bull')
)

select
    c.path, c.segment, c.month_end_date,
    c.theoretical_capacity, c.blended_capacity, c.new_logo_capacity,
    coalesce(p.pipeline_supported_bookings, 0) as pipeline_supported_bookings,
    least(c.new_logo_capacity, coalesce(p.pipeline_supported_bookings, 0)) as constrained_new_logo_arr,
    case when c.new_logo_capacity <= coalesce(p.pipeline_supported_bookings, 0) then 'Capacity' else 'Pipeline' end
        as binding_constraint,
    h.incremental_hires
from capacity_all c
left join pipeline_all p on p.path = c.path and p.segment = c.segment and p.month_end_date = c.month_end_date
join hires_by_path h on h.path = c.path and h.segment = c.segment
order by c.path, c.segment, c.month_end_date
