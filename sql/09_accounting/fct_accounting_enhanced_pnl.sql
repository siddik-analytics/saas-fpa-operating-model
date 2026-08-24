-- ACCOUNTING-ENHANCED ANALYTICAL VIEW of Sales & Marketing and operating income.
-- Grain: path x month, Jan-2024 .. Dec-2027.
--
-- THIS IS NOT THE OFFICIAL BASE FORECAST AND DOES NOT REPLACE ANYTHING.
--   fct_pnl_reforecast is frozen Phase 6 output. It is read here and never written. Nothing
--   downstream of Phase 6 consumes this model; the ARR waterfall, the scenarios, the runway, the
--   hiring decision and every Phase 7 bridge continue to run off the Phase 6 P&L exactly as
--   before. Control L proves that the frozen lines this model reads back out are bit-identical
--   to the ones Phase 6 published.
--
--   What this model is for: showing a reader what Helio's S&M and operating income would look
--   like if the forecast carried a real ASC 340-40 commission rollforward instead of the flat
--   amortisation run rate Phase 6 deliberately parked there.
--
--       Phase 6 Sales & Marketing Expense
--       - Phase 6 simplified commission treatment  (6030 formula + flat 6040 run rate)
--       + ASC 340-40 GAAP commission expense       (immediate expense + real amortisation)
--       = Accounting-enhanced Sales & Marketing Expense
--
--   and the same single adjustment carried down to operating income. Every other P&L line is
--   passed through untouched, because commission accounting is the only thing this phase changes.
--
-- CAPITALISATION IS A TIMING EFFECT, NOT A SAVING, and the model is built so a reader cannot
-- miss it. Cash commission is carried alongside GAAP commission expense on every row. In a
-- growing book, capitalising 59% of newly earned commission and releasing prior cohorts over 36
-- months defers expense and flatters near-term operating income; the cash left the business on
-- the original payment schedule regardless. The cumulative_expense_deferred column is the
-- running size of that timing benefit -- it is the commission asset by another name, and it
-- reverses in full over the following 36 months.
select
    p.path,
    p.month_end_date,
    d.fiscal_year,
    d.fiscal_quarter,
    p.is_actual,
    p.period_label,

    -- Frozen Phase 6 lines, read unchanged
    p.total_revenue                 as phase6_total_revenue,
    p.gross_profit                  as phase6_gross_profit,
    p.sales_marketing               as phase6_sales_marketing,
    p.total_opex                    as phase6_total_opex,
    p.operating_income              as phase6_operating_income,

    -- The commission treatments being swapped
    r.phase6_total_commission_expense as phase6_commission_treatment,
    r.asc340_gaap_commission_expense,
    r.asc340_immediate_expense,
    r.asc340_amortisation,
    r.commission_accounting_adjustment,

    -- Accounting-enhanced analytical view
    p.sales_marketing  + r.commission_accounting_adjustment as enhanced_sales_marketing,
    p.total_opex       + r.commission_accounting_adjustment as enhanced_total_opex,
    p.operating_income - r.commission_accounting_adjustment as enhanced_operating_income,
    case when p.total_revenue > 0
         then (p.operating_income - r.commission_accounting_adjustment) / p.total_revenue end
        as enhanced_operating_margin,
    case when p.total_revenue > 0 then p.operating_income / p.total_revenue end
        as phase6_operating_margin,
    case when p.total_revenue > 0
         then r.commission_accounting_adjustment / p.total_revenue end
        as adjustment_pct_of_revenue,

    -- Cash economics, kept on the same row as the expense so the two can never be confused
    r.commission_earned,
    r.commission_paid_cash,
    r.asc340_gaap_commission_expense - r.commission_paid_cash as gaap_less_cash_commission,
    r.ending_commission_asset as cumulative_expense_deferred
from fct_pnl_reforecast p
join fct_commission_accounting_reconciliation r
  on r.path = p.path and r.month_end_date = p.month_end_date
join dim_date d on d.month_end_date = p.month_end_date
order by p.path, p.month_end_date
