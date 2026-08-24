-- Three-way subscription-revenue comparison, month by month, Jan-2024 .. Jun-2026:
--
--   A  Contract analytical revenue   int_contract_billing_schedule -- each contract's observed
--                                    monthly in-force MRR, recognised at month grain
--   B  Source GL actual revenue      fact_gl_actuals accounts 4000 + 4010, sign-flipped from the
--                                    ledger's natural credit
--   C  Phase 6 management revenue    fct_pnl_reforecast, Base path (identical to B in actual
--                                    months by construction -- Phase 6 reads the GL unchanged)
--
-- WHAT A IS. A contract-level MONTHLY RATABLE ANALYTICAL revenue schedule. It is more
-- contract-granular than B, because it is built per contract from that contract's own rate and
-- cadence rather than from a company-level ARR blend. It is NOT a full ASC 606 subledger: no
-- daily service-period proration for mid-month commencement or termination, no invoice dates,
-- no standalone-selling-price allocation. Both A and B are therefore analytical conventions at
-- different levels of granularity, and neither is "the right answer" that the other approximates.
--
-- THIS MODEL DOES NOT REPLACE PHASE 6. Phase 6 revenue is frozen and is read here, never
-- written. The contract schedule is an enhancement layer that shows what a more granular monthly
-- recognition method produces and quantifies the gap; where the two differ, the difference is
-- explained, not closed.
--
-- WHY THERE IS A DIFFERENCE, and why it is a difference in convention rather than an accounting
-- error in either series. The source ledger recognises subscription revenue as a WEIGHTED LAG OF
-- PRIOR-MONTH-END ARR -- 55% of month-1 ARR plus 45% of month-2 ARR, divided by 12 (config
-- gl.subscription_revenue_lag_weights) -- because contracts start mid-month, provisioning lags
-- signature, and that convention is what lands the FY2025 quarterly series on the Phase 1
-- anchors. The contract schedule recognises the CURRENT month's in-force rate. In a business
-- growing ~1.5% a month, recognising this month instead of a blend of the two prior months runs
-- structurally ahead, by roughly one and a half months of growth. The difference is therefore
-- expected to be small, positive and stable. It is reported every month, and control D bounds
-- it rather than eliminating it. Neither series is corrected toward the other.
--
-- JAN-2024 IS A SOURCE BOUNDARY ARTIFACT, EXCLUDED FROM THE TOLERANCE TEST AND SAID SO. The
-- ledger's lag convention needs two prior ARR balances; at Jan-2024, the first ledger month,
-- only one exists, so the generator's 45%-weighted second lag resolves against zero and posts
-- roughly 55% of a normal month. That is a property of where fact_gl_actuals starts, not of
-- this reconciliation. The month is published with its 85% residual visible and is excluded
-- from control D, which tests Feb-2024 onward.
--
-- SERVICES REVENUE IS MEMO ONLY. Accounts 4100 / 4110 are carried here for completeness of the
-- P&L picture but are NOT part of the contract schedule or the deferred-revenue rollforward:
-- the source generates implementation-fee revenue ratably over the initial term and delivered
-- professional services in the first three months of a project, but stores no billing event for
-- either (docs/generation_methodology.md section 9). Inventing a services billing cadence to
-- create services deferred revenue is exactly the fabrication this phase refuses to do.
with contract_revenue as (
    select
        month_end_date,
        sum(subscription_revenue_recognised) as contract_accounting_revenue
    from int_contract_billing_schedule
    where month_end_date between date '2024-01-31' and date '2026-06-30'
    group by 1
),

gl_revenue as (
    select
        month_end_date,
        sum(case when account_code in (4000, 4010) then -actual_amount else 0 end)::double
            as gl_subscription_revenue,
        sum(case when account_code = 4000 then -actual_amount else 0 end)::double
            as gl_recurring_revenue,
        sum(case when account_code = 4010 then -actual_amount else 0 end)::double
            as gl_usage_revenue,
        sum(case when account_code in (4100, 4110) then -actual_amount else 0 end)::double
            as gl_services_revenue_memo
    from stg_fact_gl_actuals
    where month_end_date between date '2024-01-31' and date '2026-06-30'
    group by 1
),

phase6_revenue as (
    select month_end_date, subscription_revenue::double as phase6_subscription_revenue
    from fct_pnl_reforecast
    where path = 'Base' and is_actual
      and month_end_date between date '2024-01-31' and date '2026-06-30'
)

select
    c.month_end_date,
    d.fiscal_year,
    d.fiscal_quarter,
    c.contract_accounting_revenue,
    g.gl_subscription_revenue,
    g.gl_recurring_revenue,
    g.gl_usage_revenue,
    p.phase6_subscription_revenue,
    c.contract_accounting_revenue - g.gl_subscription_revenue as residual_vs_gl,
    case when g.gl_subscription_revenue > 0
         then c.contract_accounting_revenue / g.gl_subscription_revenue - 1 end
        as residual_vs_gl_pct,
    p.phase6_subscription_revenue - g.gl_subscription_revenue as phase6_vs_gl,
    g.gl_services_revenue_memo,
    (c.month_end_date = date '2024-01-31') as is_ledger_boundary_month,
    case when c.month_end_date = date '2024-01-31'
         then 'Ledger boundary - GL lag convention has only one prior ARR balance'
         else 'Recognition timing - GL lags ARR 55/45 over two months, schedule recognises current month'
    end as residual_explanation
from contract_revenue c
join gl_revenue g   on g.month_end_date = c.month_end_date
join phase6_revenue p on p.month_end_date = c.month_end_date
join dim_date d     on d.month_end_date = c.month_end_date
order by c.month_end_date
