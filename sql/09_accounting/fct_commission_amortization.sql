-- ASC 340-40 amortisation of capitalised contract-acquisition cost, by capitalisation cohort.
-- Grain: path x capitalisation_cohort_month x month. Straight line, 36 months, beginning in the
-- month the cost is capitalised.
--
-- THE 36-MONTH USEFUL LIFE, AND WHY IT IS NOT THE INITIAL CONTRACT TERM.
--   ASC 340-40-35-1 requires amortisation on a systematic basis consistent with the transfer of
--   the goods or services to which the asset relates -- the PERIOD OF EXPECTED BENEFIT, which
--   includes anticipated renewals where the entity does not pay a commensurate commission on
--   those renewals. Helio's initial contract term is 12 months on 61% of ARR. Amortising a
--   new-logo commission over 12 months would be wrong here, because:
--
--     Renewal commission is NOT commensurate with the initial commission. New Logo pays 9% of
--     ACV; a renewal pays 3% and only on the UPLIFT, not on the renewed base (config
--     sales_reps.commission_rate_new vs commission_rate_renewal_uplift). A renewal therefore
--     costs the business roughly a thirtieth of what the land cost. When the renewal commission
--     is not commensurate, the initial commission is understood to relate to the renewal
--     periods as well, and the amortisation period must extend beyond the initial term.
--
--   36 months is the frozen figure (PHASE1_SPEC 8.7, config gl.commission_amortisation_months).
--   It is CONSERVATIVE against the cohort evidence rather than generous: TTM logo retention at
--   30 Jun 2026 is 83.4% company-wide, implying an average customer life near six years, and
--   only SMB (78.7% logo retention, ~4.7 years) comes within reach of three. The project holds
--   36 months anyway. fct_commission_sensitivity publishes 24 and 60 months alongside, as
--   PHASE1_SPEC 8.7 requires, so the judgement is visible instead of asserted.
--
-- AMORTISATION BEGINS IN THE MONTH OF CAPITALISATION, never before it, and the cohort structure
-- makes that structurally impossible: a cohort row cannot exist at a month earlier than its own
-- cohort month, and no row exists past month 35 of the cohort. Controls H and I check both.
--
-- NO IMPAIRMENT AND NO WRITE-OFF LINE EXISTS, and that is a source limitation, not an omission.
-- ASC 340-40-35-3 requires an impairment charge when the carrying amount exceeds the remaining
-- consideration expected. The source carries no contract-level link from a commission to the
-- customer that later churned -- fct_crm_opportunity's account_id is a real customer only for
-- provisioned wins, and the capitalised pool is blended at 59% of all earned commission rather
-- than tracked per contract. Manufacturing write-off events would be fabricating accounting
-- precision the source does not support, so the rollforward has no impairment line at all
-- rather than a plausible-looking invented one.
with cohort as (
    select
        path,
        month_end_date as cohort_month,
        sum(capitalised_amount) as capitalised_amount
    from int_commission_earned
    group by 1, 2
    having sum(capitalised_amount) <> 0
),

schedule as (
    select
        c.path,
        c.cohort_month,
        c.capitalised_amount,
        g.k::integer as months_elapsed,
        last_day(date_trunc('month', c.cohort_month) + to_months(g.k::integer)) as month_end_date,
        c.capitalised_amount / 36.0 as monthly_amortisation
    from cohort c
    cross join generate_series(0, 35) g(k)
)

select
    s.path,
    s.cohort_month,
    s.month_end_date,
    d.fiscal_year,
    d.fiscal_quarter,
    s.months_elapsed,
    36 as useful_life_months,
    s.capitalised_amount,
    s.monthly_amortisation,
    s.capitalised_amount * (s.months_elapsed + 1) / 36.0 as cumulative_amortisation,
    s.capitalised_amount * (35 - s.months_elapsed)  / 36.0 as unamortised_balance,
    (s.months_elapsed = 35) as is_final_amortisation_month
from schedule s
join dim_date d on d.month_end_date = s.month_end_date
-- Cohorts booked late in the horizon amortise past it: a Dec-2027 cohort runs to Nov-2030. Those
-- months are truncated at the calendar's own end rather than reported against months dim_date
-- does not have. The consequence is stated in the report: the Dec-2027 closing commission asset
-- is a real unamortised balance with a scheduled runoff beyond the modelled horizon, not a
-- balance that disappears.
where s.month_end_date <= date '2027-12-31'
order by s.path, s.cohort_month, s.month_end_date
