-- Capitalised commission asset rollforward, and the cash-versus-GAAP commission view.
-- Grain: path x month, Jan-2024 .. Dec-2027.
--
--   Beginning Capitalised Commission Asset
--   + New Capitalised Commission
--   - Amortisation
--   = Ending Capitalised Commission Asset
--
-- There is no fourth line. No write-offs, no impairment, no plug -- see
-- fct_commission_amortization on why an impairment line the source cannot support is left out
-- rather than invented. Control G checks the identity at every path-month.
--
-- THE ASSET IS ANALYTICALLY DERIVED, NOT GL-RECONCILED, AND THE DISTINCTION IS LOAD-BEARING.
--   fact_gl_actuals is a P&L extract. It carries accounts 6030 Sales Commissions and 6040
--   Commission Amortisation and no balance sheet at all, so no capitalised-commission balance
--   exists in the source to tie to. What can be said, and is said precisely:
--
--       P&L expense reconciled     -- immediate expense ties to 6030 and amortisation ties to
--                                     6040, both to the cent, every actual month (controls D/K)
--       Asset analytically derived -- the balance is the arithmetic consequence of those two
--                                     reconciled flows, not an independently verified balance
--
--   OPENING BALANCE IS ZERO AT 1 JAN 2024, AND THAT UNDERSTATES THE REAL ASSET. fact_gl_actuals
--   begins Jan-2024, so account 6040 amortises only Jan-2024-and-later cohorts; Helio has been
--   selling since 2019 and a real balance sheet would carry unamortised cost from 2021-2023
--   bookings too. The schedule adopts the ledger's own cohort window so the P&L ties exactly,
--   and the resulting asset is therefore a Jan-2024-forward COHORT balance, not a full
--   balance-sheet carrying amount. Quantified in the validation report's limitations section.
--
-- CASH VERSUS GAAP -- three different numbers that are all correct.
--   Commission EARNED is what the seller books on signature.
--   Commission PAID is cash out of the door: PHASE1_SPEC 8.7 pays 50% on booking and 50% on
--   cash collection, and collection follows the source's own collections curve (config
--   cash.collections_curve, 18/46/28/8 across months 0-3, consistent with the 42-day DSO). Paid
--   in month m is therefore 59% of month m's earned plus 23% / 14% / 4% of the three prior
--   months' -- the 0.50 booking half plus 0.50 x the curve.
--   GAAP COMMISSION EXPENSE is immediate expense plus amortisation, and matches neither.
--   Capitalising commission does not reduce the cash cost by one dollar; it moves when the cost
--   hits the P&L. The accrued commission liability rolls forward here to make that explicit.
--
--   The accrued liability opens at zero for the same left-censoring reason as the asset, and its
--   closing balance at Dec-2027 is the genuine unpaid tail on Q4-2027 bookings.
with earned as (
    select
        path,
        month_end_date,
        sum(commission_earned)   as commission_earned,
        sum(immediate_expense)   as immediate_expense,
        sum(capitalised_amount)  as capitalised_amount,
        bool_and(is_actual)      as is_actual
    from int_commission_earned
    group by 1, 2
),

month_seq as (
    select month_end_date, row_number() over (order by month_end_date) as rn
    from dim_date
    where month_end_date between date '2024-01-31' and date '2027-12-31'
),

spine as (
    select p.path, m.month_end_date, m.rn
    from month_seq m
    cross join (select distinct path from earned) p
),

amortised as (
    select path, month_end_date, sum(monthly_amortisation) as amortisation
    from fct_commission_amortization
    group by 1, 2
),

paid as (
    -- 50% on booking + 50% spread over the collections curve (0.18 / 0.46 / 0.28 / 0.08).
    select
        s.path,
        s.month_end_date,
        0.59 * coalesce(e0.commission_earned, 0)
      + 0.23 * coalesce(e1.commission_earned, 0)
      + 0.14 * coalesce(e2.commission_earned, 0)
      + 0.04 * coalesce(e3.commission_earned, 0) as commission_paid_cash
    from spine s
    left join earned e0 on e0.path = s.path and e0.month_end_date = s.month_end_date
    left join month_seq m1 on m1.rn = s.rn - 1
    left join earned e1 on e1.path = s.path and e1.month_end_date = m1.month_end_date
    left join month_seq m2 on m2.rn = s.rn - 2
    left join earned e2 on e2.path = s.path and e2.month_end_date = m2.month_end_date
    left join month_seq m3 on m3.rn = s.rn - 3
    left join earned e3 on e3.path = s.path and e3.month_end_date = m3.month_end_date
),

flows as (
    select
        s.path,
        s.month_end_date,
        s.rn,
        coalesce(e.commission_earned, 0)  as commission_earned,
        coalesce(e.immediate_expense, 0)  as immediate_expense,
        coalesce(e.capitalised_amount, 0) as capitalised_amount,
        coalesce(a.amortisation, 0)       as amortisation,
        coalesce(pd.commission_paid_cash, 0) as commission_paid_cash,
        coalesce(e.is_actual, s.month_end_date <= date '2026-06-30') as is_actual
    from spine s
    left join earned e   on e.path = s.path and e.month_end_date = s.month_end_date
    left join amortised a on a.path = s.path and a.month_end_date = s.month_end_date
    left join paid pd    on pd.path = s.path and pd.month_end_date = s.month_end_date
),

balances as (
    select
        f.*,
        sum(f.capitalised_amount - f.amortisation) over
            (partition by f.path order by f.rn rows between unbounded preceding and current row)
            as ending_commission_asset,
        sum(f.commission_earned - f.commission_paid_cash) over
            (partition by f.path order by f.rn rows between unbounded preceding and current row)
            as ending_accrued_commission_liability
    from flows f
)

select
    b.path,
    b.month_end_date,
    d.fiscal_year,
    d.fiscal_quarter,
    -- Asset rollforward
    b.ending_commission_asset - (b.capitalised_amount - b.amortisation) as beginning_commission_asset,
    b.capitalised_amount as capitalised_commission,
    b.amortisation       as commission_amortisation,
    0.0                  as commission_impairment,
    b.ending_commission_asset,
    -- Earned / expensed / capitalised identity
    b.commission_earned,
    b.immediate_expense,
    b.immediate_expense + b.capitalised_amount as earned_recomposed,
    -- GAAP versus cash
    b.immediate_expense + b.amortisation as gaap_commission_expense,
    b.commission_paid_cash,
    (b.immediate_expense + b.amortisation) - b.commission_paid_cash as gaap_less_cash_commission,
    b.ending_accrued_commission_liability
        - (b.commission_earned - b.commission_paid_cash) as beginning_accrued_commission_liability,
    b.ending_accrued_commission_liability,
    b.is_actual,
    case
        when b.is_actual then 'Actual'
        when b.month_end_date <= date '2026-12-31' then 'FY2026 Reforecast'
        else 'Forward Runway Projection'
    end as period_label
from balances b
join dim_date d on d.month_end_date = b.month_end_date
order by b.path, b.month_end_date
