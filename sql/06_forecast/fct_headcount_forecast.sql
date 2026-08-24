-- Monthly headcount rollforward by function, path x month. Actuals (dim_date.is_actual) are a
-- real beginning/hires/departures/ending rollforward computed straight from dim_employee,
-- replicated identically across every path. Forecast months apply a closed-form survival
-- (expected-value, fractional headcount -- the same convention fact_forecast's own benchmark
-- Ending Headcount line uses) rather than a random departure draw:
--
--   existing headcount   30 Jun 2026 actual headcount(function) x (1 - monthly_hazard)^t
--   + each hire cohort    hire_count x (1 - monthly_hazard)^(months since that cohort's own hire month)
--   = ending headcount(function, path, month)
--
-- monthly_hazard is the BINDING Phase 1 policy rate (employees.annual_attrition_by_function /
-- sales_reps.annual_attrition), converted to a monthly hazard -- not the historical generated
-- series, which dim_employee itself confirms carries zero known future terminations past the
-- reporting date, and which the source docs flag as running hot in Sales for calibration
-- reasons unrelated to a forward planning rate. See docs/forecast_runway.md.
--
-- Hire cohorts: every currently OPEN requisition (every function, not Sales alone), assumed to
-- fill on a single documented date (config: forecast.open_req_assumed_fill_date), scenario-
-- invariant; plus, Sales only, the incremental hires int_gtm_capacity_pipeline_forecast computed
-- from the capacity gap, starting config: forecast.incremental_hire_start_month, present only in
-- the two hiring-case paths (Base_Targeted, Base_FullClose).
--
-- Departures(month) is the residual that makes the identity hold exactly:
--   Beginning + Hires - Departures = Ending
with paths as (
    select 'Bear' as path union all select 'Base' union all select 'Bull'
    union all select 'Base_Targeted' union all select 'Base_FullClose'
),

functions as (
    select 'Sales' as function union all select 'Marketing' union all select 'Customer Success'
    union all select 'Support & Cloud Ops' union all select 'Professional Services'
    union all select 'Engineering' union all select 'Product & Design' union all select 'G&A'
),

-- Point-in-time "active as of D" is hire_date <= D and (termination_date is null or
-- termination_date > D) -- exclusive at the termination boundary, so an employee terminated
-- exactly on the reporting date is not double-counted as still "on the books" at that same
-- instant. This is what reproduces the PHASE1_SPEC-analogous 206-headcount anchor at 30 Jun 2026
-- exactly (int_rep_month.sql's own "active for a month" flag is a different, inclusive concept --
-- did this rep work at all during the month -- not a point-in-time headcount snapshot).
-- Beginning/Hires/Departures are then derived from two point-in-time Ending snapshots (this
-- month-end and the prior actual month-end) rather than from independent boundary conditions, so
-- the rollforward identity holds by construction instead of by hoping two separately-written
-- boundary conditions agree.
actual_months as (
    select month_end_date, row_number() over (order by month_end_date) as rn
    from dim_date where is_actual
),

actual_months_with_prior as (
    select am.month_end_date, am.rn,
           lag(am.month_end_date) over (order by am.rn) as prior_month_end_date
    from actual_months am
),

ending_actual as (
    select f.function, am.month_end_date,
           count(e.employee_id) as ending_headcount
    from functions f
    cross join actual_months am
    left join dim_employee e
        on e.function = f.function
       and e.hire_date <= am.month_end_date
       and (e.termination_date is null or e.termination_date > am.month_end_date)
    group by 1, 2
),

hires_actual as (
    select f.function, amp.month_end_date,
           count(e.employee_id) as hires
    from functions f
    cross join actual_months_with_prior amp
    left join dim_employee e
        on e.function = f.function
       and amp.prior_month_end_date is not null
       and e.hire_date > amp.prior_month_end_date
       and e.hire_date <= amp.month_end_date
    group by 1, 2
),

actual_headcount as (
    select
        ea.function, ea.month_end_date,
        coalesce(lag(ea.ending_headcount) over (partition by ea.function order by ea.month_end_date),
                  ea.ending_headcount) as beginning_headcount,
        ha.hires,
        coalesce(lag(ea.ending_headcount) over (partition by ea.function order by ea.month_end_date),
                  ea.ending_headcount) + ha.hires - ea.ending_headcount as departures,
        ea.ending_headcount
    from ending_actual ea
    join hires_actual ha on ha.function = ea.function and ha.month_end_date = ea.month_end_date
),

actual_rows as (
    select p.path, a.function, a.month_end_date, a.beginning_headcount, a.hires, a.departures,
           a.ending_headcount, true as is_actual
    from actual_headcount a
    cross join paths p
),

jun2026_headcount as (
    select function, ending_headcount as headcount
    from actual_headcount
    where month_end_date = date '2026-06-30'
),

hazard_by_function as (
    -- config/assumptions.yml: employees.annual_attrition_by_function -- GROSS voluntary
    -- attrition. Only every currently open req and the two hiring-case incremental cohorts are
    -- modelled as explicit future hire events; ordinary-course backfill hiring for attrition
    -- occurring AFTER those known events is not separately simulated hire-by-hire (that would
    -- require synthesising hire dates for hypothetical future backfills the source data cannot
    -- support). Instead, the existing population's decay uses the NET rate implied by config's
    -- own requisitions.backfill_rate = 0.78 (gross rate x (1 - backfill_rate)) -- i.e., 78% of
    -- ordinary attrition is assumed replaced in the normal course, exactly as the source data's
    -- own backfill_rate driver states, without individually dated backfill cohorts. Applying the
    -- full GROSS rate with no backfill at all would decay total headcount by roughly a fifth
    -- over the 18-month horizon, which is not a defensible planning assumption and is not what
    -- config's own backfill_rate driver describes. See docs/forecast_runway.md.
    select 'Sales' as function, 0.26 as annual_rate
    union all select 'Marketing', 0.20
    union all select 'Customer Success', 0.21
    union all select 'Support & Cloud Ops', 0.19
    union all select 'Professional Services', 0.17
    union all select 'Engineering', 0.13
    union all select 'Product & Design', 0.14
    union all select 'G&A', 0.11
),

monthly_hazard as (
    select function, 1 - power(1 - annual_rate * (1 - 0.78), 1.0 / 12.0) as monthly_hazard
    from hazard_by_function
),

open_req_hires as (
    select function, count(*) as hire_count, date '2026-08-31' as hire_month
    from stg_fact_requisition
    where status = 'Open'
    group by 1
),

incremental_hires_by_segment as (
    -- incremental_hires is a STOCK (the total hire count for that path/segment), repeated on
    -- every month's row in int_gtm_capacity_pipeline_forecast -- take it once per (path, segment),
    -- never summed across months, or it would be counted once per forecast month.
    select distinct path, segment, incremental_hires
    from int_gtm_capacity_pipeline_forecast
    where path in ('Base_Targeted', 'Base_FullClose')
),

incremental_sales_hires as (
    select path, sum(incremental_hires) as hire_count, date '2026-10-31' as hire_month
    from incremental_hires_by_segment
    group by 1
    having sum(incremental_hires) > 0
),

hire_cohorts as (
    select p.path, o.function, o.hire_month, o.hire_count
    from open_req_hires o
    cross join paths p
    union all
    select i.path, 'Sales' as function, i.hire_month, i.hire_count
    from incremental_sales_hires i
),

forecast_months as (
    select month_end_date from dim_date where is_forecast and month_end_date <= date '2027-12-31'
),

existing_survival as (
    select p.path, f.function, fm.month_end_date,
           coalesce(j.headcount, 0) * power(1 - mh.monthly_hazard,
               date_diff('month', date '2026-06-30', fm.month_end_date)) as survived
    from functions f
    cross join forecast_months fm
    cross join paths p
    left join jun2026_headcount j on j.function = f.function
    join monthly_hazard mh on mh.function = f.function
),

hire_survival as (
    select
        hc.path, hc.function, fm.month_end_date,
        hc.hire_count * power(1 - mh.monthly_hazard,
            greatest(0, date_diff('month', hc.hire_month, fm.month_end_date))) as survived
    from hire_cohorts hc
    cross join forecast_months fm
    join monthly_hazard mh on mh.function = hc.function
    where fm.month_end_date >= hc.hire_month
),

ending_components as (
    select path, function, month_end_date, sum(survived) as ending_headcount
    from (
        select path, function, month_end_date, survived from existing_survival
        union all
        select path, function, month_end_date, survived from hire_survival
    )
    group by 1, 2, 3
),

hires_by_month as (
    select path, function, hire_month as month_end_date, sum(hire_count) as hires
    from hire_cohorts
    group by 1, 2, 3
),

forecast_rows_pre as (
    select
        ec.path, ec.function, ec.month_end_date, ec.ending_headcount,
        lag(ec.ending_headcount) over (partition by ec.path, ec.function order by ec.month_end_date) as prior_ending,
        coalesce(hbm.hires, 0) as hires
    from ending_components ec
    left join hires_by_month hbm
        on hbm.path = ec.path and hbm.function = ec.function and hbm.month_end_date = ec.month_end_date
),

forecast_rows as (
    select
        frp.path, frp.function, frp.month_end_date,
        coalesce(frp.prior_ending, j.headcount) as beginning_headcount,
        frp.hires,
        coalesce(frp.prior_ending, j.headcount) + frp.hires - frp.ending_headcount as departures,
        frp.ending_headcount,
        false as is_actual
    from forecast_rows_pre frp
    left join jun2026_headcount j on j.function = frp.function
),

combined as (
    select * from actual_rows
    union all
    select * from forecast_rows
)

select
    path, function, month_end_date, beginning_headcount, hires, departures, ending_headcount, is_actual,
    case
        when is_actual then 'Actual'
        when month_end_date <= date '2026-12-31' then 'FY2026 Reforecast'
        else 'Forward Runway Projection'
    end as period_label
from combined
order by path, function, month_end_date
