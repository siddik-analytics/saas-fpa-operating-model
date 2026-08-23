-- Sales rep capacity, one row per quota-carrying AE (dim_sales_rep) per actual reporting month
-- (int_rep_month). PHASE1_SPEC 8.9:
--   Theoretical quota capacity   = Monthly Quota x Ramp %
--   Expected productive capacity = Monthly Quota x Ramp % x Expected Attainment
-- These are NOT the same figure and are exposed as separate columns -- see docs/gtm_finance.md.
--
-- Expected Attainment is not an assumed constant: it is the trailing realised attainment of
-- FULLY-RAMPED reps (ramp_pct = 100%) across every actual month, by segment -- the same
-- "derive, never fabricate" convention (PHASE1_SPEC governing constraint 3) every other model in
-- this project follows. A rep still ramping is excluded from this average: a ramping rep's low
-- output is a ramp effect, already captured by Ramp %, and averaging it in would double-count
-- the ramp shortfall as an attainment shortfall too.
--
-- Actual bookings credit ALL THREE deal types the CRM records against a rep -- New Logo,
-- Expansion and Renewal Uplift -- because dim_sales_rep carries one blended quota and pays
-- commission on all three (commission_rate_new / _expansion, and
-- config/assumptions.yml sales_reps.commission_rate_renewal_uplift). This is a blended,
-- account-based quota model, not a New-ARR-only one; see docs/gtm_finance.md.
--
-- Eligible quota for attainment is the RAMPED monthly quota (theoretical_quota_capacity), not
-- the flat annual quota -- a rep in month 2 of ramp is measured against 25% of a month's quota,
-- matching how a new-hire quota is actually set in practice. Where that denominator is zero
-- (month 1 of ramp), actual_attainment is null, never a divide-by-zero value (PHASE1_SPEC
-- section 26, control C).
--
-- new_logo_productive_capacity is NOT the same figure as expected_productive_capacity. The
-- latter is BLENDED (all three credited deal types); comparing it directly to a New-Logo-ONLY
-- ARR target is not like-for-like. new_logo_productive_capacity = expected_productive_capacity x
-- new_logo_share_of_bookings (int_gtm_new_logo_mix, the FY2025 within-segment CRM bookings mix
-- -- see that model's header for why FY2025 and why this ratio, not a fresh one per month).
-- Both capacity figures are kept: blended for rep-productivity analysis (section 3 of
-- reports/gtm_validation_report.md), New-Logo-only for coverage against the New Logo ARR target
-- (sections 2 and 9). See docs/gtm_finance.md.
with monthly_bookings as (
    select rep_id, actual_close_month as month_end_date, sum(acv) as credited_bookings
    from int_crm_closed_won
    where rep_id is not null
    group by 1, 2
),

fully_ramped_attainment as (
    select
        rm.segment,
        avg(coalesce(mb.credited_bookings, 0) / nullif(rm.monthly_quota, 0)) as expected_attainment
    from int_rep_month rm
    left join monthly_bookings mb
        on mb.rep_id = rm.rep_id and mb.month_end_date = rm.month_end_date
    where rm.ramp_pct = 1.00
    group by 1
)

select
    rm.rep_id,
    rm.rep_name,
    rm.segment,
    rm.territory,
    rm.hire_date,
    rm.termination_date,
    rm.month_end_date,
    rm.months_since_hire,
    rm.annual_quota,
    rm.monthly_quota,
    rm.ramp_profile_id,
    rm.ramp_pct,
    fra.expected_attainment,
    rm.monthly_quota * rm.ramp_pct as theoretical_quota_capacity,
    rm.monthly_quota * rm.ramp_pct * fra.expected_attainment as expected_productive_capacity,
    nlm.new_logo_share_of_bookings,
    rm.monthly_quota * rm.ramp_pct * fra.expected_attainment * nlm.new_logo_share_of_bookings
        as new_logo_productive_capacity,
    coalesce(mb.credited_bookings, 0) as actual_bookings,
    coalesce(mb.credited_bookings, 0) / nullif(rm.monthly_quota * rm.ramp_pct, 0) as actual_attainment
from int_rep_month rm
join fully_ramped_attainment fra on fra.segment = rm.segment
join int_gtm_new_logo_mix nlm on nlm.segment = rm.segment
left join monthly_bookings mb on mb.rep_id = rm.rep_id and mb.month_end_date = rm.month_end_date
order by rm.segment, rm.rep_id, rm.month_end_date
