-- Rep x actual-month spine -- one row per quota-carrying AE (dim_sales_rep) for every actual
-- reporting month (dim_date.is_actual) the rep was employed. Built once here so
-- fct_sales_capacity, fct_rep_attainment and the cost-allocation layer all read the same ramp
-- and headcount logic, the same int_ pattern int_arr_customer_month established for the ARR
-- engine (docs/arr_engine.md).
--
-- A rep is "active" for a month if hired on or before month end and, if terminated, not
-- terminated before month start -- whole-month membership, matching how every other monthly
-- fact table in this project treats a calendar month (no daily proration anywhere in the
-- analytical layer). A terminated rep's spine simply stops at their termination month; there is
-- no row, and therefore no capacity, afterward (PHASE1_SPEC section 26, control B).
--
-- Ramp schedule (PHASE1_SPEC 8.9, binding). months_since_hire counts the hire month as month 1:
--   month 1: 0% both profiles          month 4: 75% standard / 60% enterprise
--   month 2: 25% standard / 15% ent    month 5+: 100% standard / 85%-then-100% enterprise
--   month 3: 50% standard / 35% ent    month 6+: 100% both
with reps as (
    select rep_id, rep_name, segment, territory, hire_date, termination_date,
           annual_quota, ramp_profile_id
    from dim_sales_rep
),

actual_months as (
    select month_end_date, month_start_date
    from dim_date
    where is_actual
),

spine as (
    select
        r.rep_id, r.rep_name, r.segment, r.territory, r.hire_date, r.termination_date,
        r.annual_quota, r.ramp_profile_id, m.month_end_date
    from reps r
    join actual_months m
        on m.month_end_date >= r.hire_date
       and (r.termination_date is null or r.termination_date >= m.month_start_date)
),

with_tenure as (
    select
        *,
        date_diff('month', date_trunc('month', hire_date), date_trunc('month', month_end_date)) + 1
            as months_since_hire
    from spine
)

select
    rep_id, rep_name, segment, territory, hire_date, termination_date, month_end_date,
    months_since_hire,
    annual_quota,
    annual_quota / 12.0 as monthly_quota,
    ramp_profile_id,
    case
        when ramp_profile_id = 'enterprise' then
            case
                when months_since_hire <= 1 then 0.00
                when months_since_hire = 2 then 0.15
                when months_since_hire = 3 then 0.35
                when months_since_hire = 4 then 0.60
                when months_since_hire = 5 then 0.85
                else 1.00
            end
        else
            case
                when months_since_hire <= 1 then 0.00
                when months_since_hire = 2 then 0.25
                when months_since_hire = 3 then 0.50
                when months_since_hire = 4 then 0.75
                else 1.00
            end
    end as ramp_pct
from with_tenure
order by rep_id, month_end_date
