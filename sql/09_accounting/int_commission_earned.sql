-- Commission earned, and its ASC 340-40 split into the portion expensed as incurred and the
-- portion capitalised as an incremental cost of obtaining a contract.
-- Grain: path x month x deal_type x basis. Jan-2024 .. Dec-2027.
--
-- ELIGIBILITY -- what is incremental, and what is not.
--   ASC 340-40-25-1 capitalises the incremental costs of obtaining a contract: costs that would
--   NOT have been incurred had the contract not been obtained. Sales commission earned on a
--   closed-won deal is the textbook case and is the ONLY cost this model touches. Every other
--   Sales cost in the ledger is explicitly out of scope and stays in period expense: fixed
--   Salaries & Wages (6000), Bonus (6010), Payroll Taxes & Benefits (6020), Sales Ops and
--   enablement headcount, Demand Generation (6100), Events (6110) and Brand (6120). Those are
--   incurred whether or not any individual deal closes, so they are not incremental. Nothing in
--   this phase reclassifies them.
--
-- COMMISSION BASIS AND RATES -- approved, never invented.
--   Historical months read closed-won CRM opportunities (int_crm_closed_won) and apply the
--   project's existing rates by deal type: New Logo 9%, Expansion 6%, Renewal Uplift 3%
--   (config sales_reps.commission_rate_new / _expansion / _renewal_uplift; dim_sales_rep carries
--   the first two per rep). The basis is opportunity ACV, which is the commercial basis the
--   source ledger itself used. Lost and open opportunities earn nothing. Closed-won deals that
--   never provision are INCLUDED -- the rep earned the commission on signature, and the ~3% of
--   wins that never activate is a provisioning outcome, not a commission reversal; that is the
--   same population the ledger commissioned.
--
--   ACCELERATORS ARE NOT MODELLED, and this is a deliberate refusal. PHASE1_SPEC 8.7 describes
--   accelerators above 100% attainment, but the source ledger applies flat rates with no
--   attainment kicker (src/gen_financials.py _commission_rows). Adding an accelerator here
--   would break the exact tie to account 6030 and would be inventing commission dollars the
--   business never paid. The divergence is documented rather than modelled.
--
-- FORECAST MONTHS INHERIT THE FROZEN PHASE 6 COMMERCIAL PATH AND CHANGE NOTHING IN IT.
--   Jul-2026 onward reads fct_arr_forecast unchanged and applies exactly the commission base
--   Phase 6 already uses: New Logo ARR x 9% + max(Expansion ARR, 0) x 6%, per path
--   (fct_pnl_reforecast commission_expense). No renewal-uplift component exists forward, because
--   fct_arr_forecast does not split renewal uplift out of expansion and inventing that split
--   would be a new forecast assumption. Bookings and ARR are read, never rewritten: this phase
--   computes the ACCOUNTING CONSEQUENCE of the frozen forecast, not a new forecast.
--
--   The historical basis (CRM opportunity ACV) and the forecast basis (ARR movement) are not the
--   same measurement. That discontinuity at the Jun/Jul-2026 cutover is inherited from Phase 6,
--   is quantified in the validation report, and is not smoothed away here.
--
-- THE CAPITALISATION SPLIT IS THE FROZEN ENTITY POLICY RATE.
--   config gl.commission_expensed_share = 0.41: 41% of earned commission is expensed as
--   incurred and 59% is capitalised. It is a blended entity-level rate, NOT a deal-type policy,
--   and it is applied here exactly as the ledger applies it so the schedule ties to accounts
--   6030 and 6040 to the cent. A strict deal-type reading of ASC 340-40 -- capitalise New Logo
--   and Expansion, expense Renewal Uplift under the practical expedient -- is built in
--   fct_commission_sensitivity as a labelled SENSITIVITY, never substituted for the frozen
--   policy, and is not chosen because it flatters EBITDA.
with paths as (
    select 'Bear' as path union all select 'Base' union all select 'Bull'
    union all select 'Base_Targeted' union all select 'Base_FullClose'
),

commission_rate as (
    select 'New Logo' as deal_type, 0.09 as commission_rate
    union all select 'Expansion', 0.06
    union all select 'Renewal Uplift', 0.03
),

actual_earned as (
    -- Closed-won CRM opportunity ACV, bucketed to the close month. Lost and open opportunities
    -- are excluded by int_crm_closed_won itself, so no status filter is repeated here.
    select
        w.actual_close_month as month_end_date,
        w.deal_type,
        sum(w.acv)::double as eligible_basis,
        count(*)           as opportunity_count
    from int_crm_closed_won w
    where w.actual_close_month between date '2024-01-31' and date '2026-06-30'
    group by 1, 2
),

actual_rows as (
    select
        p.path,
        a.month_end_date,
        a.deal_type,
        'CRM Closed-Won ACV' as commission_basis,
        a.eligible_basis,
        r.commission_rate,
        a.opportunity_count,
        true as is_actual
    from actual_earned a
    join commission_rate r on r.deal_type = a.deal_type
    cross join paths p
),

forecast_rows as (
    select
        f.path,
        f.month_end_date,
        m.deal_type,
        'Phase 6 Forecast ARR Movement' as commission_basis,
        case m.deal_type
            when 'New Logo'  then f.new_logo_arr::double
            when 'Expansion' then greatest(f.expansion_arr::double, 0.0)
        end as eligible_basis,
        r.commission_rate,
        cast(null as bigint) as opportunity_count,
        false as is_actual
    from fct_arr_forecast f
    cross join (select 'New Logo' as deal_type union all select 'Expansion') m
    join commission_rate r on r.deal_type = m.deal_type
    where f.segment = 'Total'
      and f.month_end_date >= date '2026-07-31'
),

combined as (
    select * from actual_rows
    union all
    select * from forecast_rows
)

select
    c.path,
    c.month_end_date,
    d.fiscal_year,
    d.fiscal_quarter,
    c.deal_type,
    c.commission_basis,
    c.eligible_basis,
    c.commission_rate,
    c.opportunity_count,
    c.eligible_basis * c.commission_rate                as commission_earned,
    c.eligible_basis * c.commission_rate * 0.41         as immediate_expense,
    c.eligible_basis * c.commission_rate * (1.0 - 0.41) as capitalised_amount,
    0.41 as commission_expensed_share,
    36   as amortisation_useful_life_months,
    c.is_actual
from combined c
join dim_date d on d.month_end_date = c.month_end_date
order by c.path, c.month_end_date, c.deal_type
