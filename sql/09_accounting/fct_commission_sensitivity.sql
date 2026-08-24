-- ASC 340-40 judgement sensitivity. Grain: variant x path x month, Jan-2024 .. Dec-2027.
--
-- Two judgements drive the whole commission schedule, and neither is provable from the data.
-- PHASE1_SPEC 8.7 requires both to be published rather than asserted, so each is re-run end to
-- end here and the result is put next to the frozen policy.
--
--   USEFUL LIFE -- 24 / 36 / 60 months.
--     36 months is frozen (config gl.commission_amortisation_months). 24 months is roughly the
--     shortest defensible expected-benefit period given renewal commission is not commensurate;
--     60 months is closer to what the cohort data actually implies, since TTM logo retention of
--     83.4% at 30 Jun 2026 puts average customer life near six years. A LONGER life defers more
--     expense and grows the asset; a shorter one does the opposite. Neither is presented as an
--     improvement.
--
--   ELIGIBILITY POLICY -- blended entity rate versus a deal-type eligibility split.
--     The frozen policy expenses a blended 41% of ALL earned commission and capitalises 59%
--     (config gl.commission_expensed_share), which is what the source ledger applies and is
--     therefore what ties to accounts 6030 and 6040.
--     The deal-type eligibility variant instead splits by deal type, assuming:
--       - New Logo and Expansion commission capitalised in full, as incremental costs of
--         obtaining a contract;
--       - Renewal Uplift commission expensed in full as incurred, under the stated
--         practical-expedient interpretation (ASC 340-40-25-4, available where the amortisation
--         period would not exceed one year -- PHASE1_SPEC 8.7).
--     This is ONE defensible reading of the eligibility question, not the uniquely authoritative
--     GAAP outcome -- neither the source nor PHASE1_SPEC establishes that, and the practical
--     expedient's availability depends on facts the source does not record. It is published as a
--     sensitivity for exactly that reason.
--     Renewal Uplift is only ~1.3% of earned commission in this population, so this variant
--     capitalises materially MORE than the frozen 59% -- it defers more expense, which is worth
--     seeing because it shows the frozen policy is the more conservative of the two and was not
--     chosen to flatter EBITDA.
--
-- THE FROZEN POLICY IS ALWAYS THE PRIMARY. Nothing downstream reads this model; fct_billings,
-- fct_commission_asset, fct_accounting_enhanced_pnl and every control run off the frozen
-- 41% / 59% split at 36 months. These rows exist to be reported, not to be selected from, and
-- no variant here is presented as more correct than the frozen policy.
with variants as (
    select 'Frozen policy - 36 months' as variant, 36 as useful_life_months, false as deal_type_eligibility_split, 1 as variant_order
    union all select 'Useful life - 24 months', 24, false, 2
    union all select 'Useful life - 60 months', 60, false, 3
    union all select 'Deal-type eligibility sensitivity - 36 months', 36, true, 4
),

earned_by_type as (
    select path, month_end_date, deal_type, commission_earned
    from int_commission_earned
),

split as (
    select
        v.variant,
        v.variant_order,
        v.useful_life_months,
        v.deal_type_eligibility_split,
        e.path,
        e.month_end_date,
        sum(e.commission_earned) as commission_earned,
        sum(case
                when not v.deal_type_eligibility_split then e.commission_earned * 0.41
                when e.deal_type = 'Renewal Uplift' then e.commission_earned
                else 0.0
            end) as immediate_expense,
        sum(case
                when not v.deal_type_eligibility_split then e.commission_earned * (1.0 - 0.41)
                when e.deal_type = 'Renewal Uplift' then 0.0
                else e.commission_earned
            end) as capitalised_amount
    from earned_by_type e
    cross join variants v
    group by 1, 2, 3, 4, 5, 6
),

amortisation as (
    select
        s.variant,
        s.path,
        last_day(date_trunc('month', s.month_end_date) + to_months(g.k::integer)) as month_end_date,
        sum(s.capitalised_amount / s.useful_life_months) as amortisation
    from split s
    cross join generate_series(0, 59) g(k)
    where g.k < s.useful_life_months
    group by 1, 2, 3
),

combined as (
    select
        s.variant,
        s.variant_order,
        s.useful_life_months,
        s.deal_type_eligibility_split,
        s.path,
        s.month_end_date,
        s.commission_earned,
        s.immediate_expense,
        s.capitalised_amount,
        coalesce(a.amortisation, 0) as amortisation
    from split s
    left join amortisation a
           on a.variant = s.variant and a.path = s.path and a.month_end_date = s.month_end_date
),

balanced as (
    select
        c.*,
        sum(c.capitalised_amount - c.amortisation) over
            (partition by c.variant, c.path order by c.month_end_date
             rows between unbounded preceding and current row) as ending_commission_asset
    from combined c
)

select
    b.variant,
    b.variant_order,
    b.useful_life_months,
    b.deal_type_eligibility_split,
    b.path,
    b.month_end_date,
    d.fiscal_year,
    b.commission_earned,
    b.immediate_expense,
    b.capitalised_amount,
    b.amortisation,
    b.immediate_expense + b.amortisation as gaap_commission_expense,
    b.ending_commission_asset,
    (b.month_end_date <= date '2026-06-30') as is_actual
from balanced b
join dim_date d on d.month_end_date = b.month_end_date
where b.month_end_date between date '2024-01-31' and date '2027-12-31'
order by b.variant_order, b.path, b.month_end_date
