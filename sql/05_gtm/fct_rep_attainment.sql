-- Rep attainment rollup, one row per quota-carrying AE per reporting period. Two periods,
-- matching the TTM convention fct_retention_ttm already established (docs/retention_renewals.md):
-- 'FY2025' (the reconciling year) and 'TTM_2026_06' (trailing twelve months to the reporting
-- date). Sums monthly credited bookings and monthly ramped ("eligible") quota from
-- fct_sales_capacity across the period, then divides once -- more stable than averaging twelve
-- separate monthly ratios, and consistent with how attainment is actually measured, against a
-- period target rather than a monthly one.
with periods as (
    select 'FY2025' as period, date '2025-01-31' as period_start, date '2025-12-31' as period_end
    union all
    select 'TTM_2026_06', date '2025-07-31', date '2026-06-30'
),

rep_period as (
    select
        c.rep_id, c.rep_name, c.segment, c.hire_date, c.termination_date,
        p.period, p.period_start, p.period_end,
        max(c.months_since_hire) as months_since_hire_at_period_end,
        sum(c.theoretical_quota_capacity) as eligible_quota,
        sum(c.actual_bookings) as credited_bookings,
        count(*) as active_months,
        sum(case when c.ramp_pct = 1.00 then 1 else 0 end) as fully_ramped_months
    from fct_sales_capacity c
    join periods p on c.month_end_date between p.period_start and p.period_end
    group by 1, 2, 3, 4, 5, p.period, p.period_start, p.period_end
)

select
    rep_id, rep_name, segment, hire_date, termination_date, period,
    active_months, fully_ramped_months, months_since_hire_at_period_end,
    eligible_quota, credited_bookings,
    credited_bookings / nullif(eligible_quota, 0) as attainment,
    (termination_date is not null and termination_date between period_start and period_end)
        as terminated_in_period
from rep_period
order by period, segment, rep_id
