-- Commission expense reconciled three ways, path x month, Jan-2024 .. Dec-2027:
--
--   A  ASC 340-40 schedule    immediate expense + amortisation of the capitalised pool
--                             (fct_commission_asset)
--   B  Source GL actual       account 6030 Sales Commissions + account 6040 Commission
--                             Amortisation, actual months only
--   C  Phase 6 simplified     what fct_pnl_reforecast actually carries inside Sales & Marketing
--
-- SIGN CONVENTION, stated because it is the easiest thing to get silently wrong.
-- fact_gl_actuals stores expenses as positive debits and revenue as negative credits
-- (docs/data_dictionary.md). Accounts 6030 and 6040 are expenses and are therefore already
-- positive in the ledger; they are read here with NO sign flip. Every commission column in this
-- model is a positive expense. A negative would mean a credit to commission expense, which this
-- schedule never produces.
--
-- WHAT PHASE 6 ACTUALLY DOES, and why the adjustment isolates exactly one thing.
--   Actual months: fct_pnl_reforecast reads fact_gl_actuals unchanged, so C = B by construction.
--   Forecast months, per fct_pnl_reforecast:
--     - the 6030-equivalent is 0.41 x (New Logo ARR x 9% + max(Expansion ARR,0) x 6%), which is
--       the SAME immediate-expense figure this schedule computes, because Phase 6 already
--       applied the frozen expensed share;
--     - the 6040-equivalent is account 6040 held FLAT at its Apr-Jun 2026 trailing-quarter
--       average inside the non-payroll run rate, because Phase 6 explicitly deferred the ASC
--       340-40 rollforward to this phase (docs/forecast_runway.md).
--
--   The accounting-enhancement adjustment is therefore, by construction, the amortisation
--   difference alone: a real ASC 340-40 rollforward of the capitalised pool versus a flat run
--   rate. In actual months the adjustment is exactly zero, because this schedule reproduces the
--   ledger rather than restating it -- which is the cleanest possible evidence that Phase 8 has
--   not moved a single historical number.
--
-- THE FLAT PHASE 6 AMORTISATION RUN RATE IS RE-DERIVED HERE FROM THE LEDGER, not typed in, so
-- that if the trailing quarter ever changes this reconciliation follows it instead of drifting
-- silently out of agreement with the P&L it claims to bridge.
with phase6_flat_amortisation as (
    select sum(actual_amount)::double / 3.0 as monthly_amount
    from stg_fact_gl_actuals
    where account_code = 6040
      and month_end_date between date '2026-04-30' and date '2026-06-30'
),

gl_actual as (
    select
        month_end_date,
        sum(case when account_code = 6030 then actual_amount else 0 end)::double as gl_commission_expense_6030,
        sum(case when account_code = 6040 then actual_amount else 0 end)::double as gl_commission_amortisation_6040
    from stg_fact_gl_actuals
    where account_code in (6030, 6040)
    group by 1
),

phase6_forecast_commission as (
    -- Reproduces fct_pnl_reforecast's own commission_expense CTE from the frozen forecast.
    select
        path,
        month_end_date,
        0.41 * (new_logo_arr::double * 0.09 + greatest(expansion_arr::double, 0.0) * 0.06)
            as phase6_commission_expense
    from fct_arr_forecast
    where segment = 'Total' and month_end_date >= date '2026-07-31'
)

select
    a.path,
    a.month_end_date,
    a.fiscal_year,
    a.fiscal_quarter,
    a.is_actual,
    a.period_label,
    -- A: ASC 340-40
    a.immediate_expense          as asc340_immediate_expense,
    a.commission_amortisation    as asc340_amortisation,
    a.gaap_commission_expense    as asc340_gaap_commission_expense,
    -- B: source GL, actual months only
    g.gl_commission_expense_6030,
    g.gl_commission_amortisation_6040,
    g.gl_commission_expense_6030 + g.gl_commission_amortisation_6040 as gl_total_commission_expense,
    a.immediate_expense       - g.gl_commission_expense_6030        as residual_immediate_vs_gl,
    a.commission_amortisation - g.gl_commission_amortisation_6040   as residual_amortisation_vs_gl,
    -- C: Phase 6 simplified treatment, as it actually sits inside fct_pnl_reforecast
    case when a.is_actual then g.gl_commission_expense_6030 else f.phase6_commission_expense end
        as phase6_commission_expense,
    case when a.is_actual then g.gl_commission_amortisation_6040 else p.monthly_amount end
        as phase6_commission_amortisation,
    case when a.is_actual
         then g.gl_commission_expense_6030 + g.gl_commission_amortisation_6040
         else f.phase6_commission_expense + p.monthly_amount end
        as phase6_total_commission_expense,
    -- The accounting-enhancement adjustment. Positive = ASC 340-40 charges MORE expense than
    -- Phase 6 carried, so enhanced operating income is LOWER.
    a.gaap_commission_expense
      - case when a.is_actual
             then g.gl_commission_expense_6030 + g.gl_commission_amortisation_6040
             else f.phase6_commission_expense + p.monthly_amount end
        as commission_accounting_adjustment,
    -- Cash view carried through so a reader never has to join two models to see the timing gap.
    a.commission_earned,
    a.commission_paid_cash,
    a.ending_commission_asset
from fct_commission_asset a
cross join phase6_flat_amortisation p
left join gl_actual g on g.month_end_date = a.month_end_date
left join phase6_forecast_commission f
       on f.path = a.path and f.month_end_date = a.month_end_date
order by a.path, a.month_end_date
