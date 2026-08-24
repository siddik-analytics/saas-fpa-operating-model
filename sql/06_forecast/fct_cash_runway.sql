-- Monthly cash roll-forward, path x month, Jul-2026 through Dec-2027. A simplified OPERATING
-- cash / burn model (PHASE1_SPEC-analogous section 28, hierarchy tier 3), not a fabricated
-- balance sheet: the source data carries no monthly cash history at all -- only the single
-- 30 Jun 2026 anchor (config: cash.cash_2026_06 = $21.8M, PHASE1_SPEC 2.3) -- and no invoice /
-- billing-schedule table this phase rebuilds, so there is no supportable monthly actual cash
-- series to show before July 2026. That single anchor is the sole starting point; everything
-- from here is forecast, for every path.
--
--   Beginning Cash
--   + Collections        config cash.collections_curve (18% / 46% / 28% / 8% over month 0-3)
--                        applied to TOTAL REVENUE as a proxy for billings -- a documented
--                        approximation; a true billings series needs contract-level billing
--                        schedules, out of scope here (docs/forecast_runway.md)
--   - Cash Operating Outflows   Total COGS + Total OpEx, LESS a Depreciation & Amortisation
--                        add-back (the one non-cash line this simplified model adjusts for;
--                        Commission Amortisation is left inside operating expense for cash
--                        purposes -- ASC 340-40 accrual/cash distinction is Phase 8 scope)
--   - Capex               0 -- no capex driver exists in the source data (config:
--                        forecast.capex_monthly), documented limitation
--   = Ending Cash
--
-- No financing of any kind -- no fundraising, no revolver draw (PHASE1_SPEC-analogous section
-- 29). If a scenario's cash goes negative, this model shows it.
with month_seq as (
    select month_end_date, row_number() over (order by month_end_date) as rn from dim_date
),

pnl as (
    select path, month_end_date, total_revenue, total_cogs, total_opex
    from fct_pnl_reforecast
    where is_actual = false
),

da_addback as (
    -- Trailing-quarter actual Depreciation & Amortisation (account 6440), the same window
    -- non_payroll_flat in fct_pnl_reforecast.sql uses -- flat forward, the one non-cash item
    -- already embedded inside the G&A non-payroll run rate.
    select sum(actual_amount) / 3.0 as monthly_da
    from stg_fact_gl_actuals
    where month_end_date between date '2026-04-30' and date '2026-06-30'
      and account_code = 6440
),

-- Actual + forecast revenue, for the collections lag lookup only -- the first three forecast
-- months' collections curve reaches back into actual Q2 2026 revenue, which `pnl` above
-- deliberately excludes (the cash rollforward itself only ever computes outflows for forecast
-- months). Without this, April/May/June actual revenue would be missing from the lag lookup and
-- July/August/September collections would come back null.
revenue_by_month as (
    select path, month_end_date, total_revenue from fct_pnl_reforecast
),

collections as (
    select
        p.path, p.month_end_date,
        0.18 * r0.total_revenue + 0.46 * r1.total_revenue + 0.28 * r2.total_revenue + 0.08 * r3.total_revenue
            as collections
    from pnl p
    join month_seq ms on ms.month_end_date = p.month_end_date
    join month_seq ms0 on ms0.rn = ms.rn
    join revenue_by_month r0 on r0.path = p.path and r0.month_end_date = ms0.month_end_date
    join month_seq ms1 on ms1.rn = ms.rn - 1
    left join revenue_by_month r1 on r1.path = p.path and r1.month_end_date = ms1.month_end_date
    join month_seq ms2 on ms2.rn = ms.rn - 2
    left join revenue_by_month r2 on r2.path = p.path and r2.month_end_date = ms2.month_end_date
    join month_seq ms3 on ms3.rn = ms.rn - 3
    left join revenue_by_month r3 on r3.path = p.path and r3.month_end_date = ms3.month_end_date
),

cash_flow as (
    select
        c.path, c.month_end_date,
        c.collections,
        (p.total_cogs + p.total_opex - da.monthly_da) as cash_operating_outflows,
        0.0 as capex,
        c.collections - (p.total_cogs + p.total_opex - da.monthly_da) - 0.0 as net_cash_flow
    from collections c
    join pnl p on p.path = c.path and p.month_end_date = c.month_end_date
    cross join da_addback da
),

rolled as (
    select
        path, month_end_date, collections, cash_operating_outflows, capex, net_cash_flow,
        21800000.0 + sum(net_cash_flow) over (
            partition by path order by month_end_date
            rows between unbounded preceding and current row
        ) as ending_cash
    from cash_flow
)

select
    path, month_end_date,
    ending_cash - net_cash_flow as beginning_cash,
    collections, cash_operating_outflows, capex, net_cash_flow,
    -1 * net_cash_flow as monthly_burn,
    ending_cash,
    case when month_end_date <= date '2026-12-31' then 'FY2026 Reforecast' else 'Forward Runway Projection' end
        as period_label
from rolled
order by path, month_end_date
