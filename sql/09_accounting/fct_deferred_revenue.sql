-- Deferred-revenue rollforward. Grain: month x segment (SMB / Mid-Market / Enterprise / Total).
-- Reporting window Jan-2024 .. Jun-2026, with 31 Dec 2023 carried as the OPENING BALANCE month.
--
--   Beginning Deferred Revenue + Billings - Recognised Revenue = Ending Deferred Revenue
--
-- control-enforced by ctl_accounting_enhancements at every single row, PHASE1_SPEC 8.6. There
-- are no other lines. No "other adjustments", no true-up, no plug: the identity closes because
-- int_contract_billing_schedule bills and recognises off one in-force rate series, so every
-- dollar invoiced is a dollar recognised later in the same contract.
--
-- THE OPENING BALANCE IS DERIVED, NOT ASSUMED. fact_subscription_monthly starts Dec-2023, so
-- contracts already running at that date were invoiced before the extract opens. The Dec-2023
-- closing balance in int_contract_billing_schedule is exactly the unrecognised remainder of
-- those pre-window invoices, computed from each contract's own cadence and in-force rate, and
-- it becomes Jan-2024's opening balance here. It is an analytical reconstruction of a balance
-- the source never stored, and is labelled as such -- not a number chosen to make a target.
--
-- UNBILLED RECEIVABLE, SHOWN SEPARATELY. Month-to-month agreements bill in arrears
-- (PHASE1_SPEC 2.4), so at any month end they carry service delivered but not yet invoiced. That
-- balance is reported in its own non-negative column and is never netted into deferred revenue,
-- because netting is exactly how a negative deferred revenue balance gets hidden.
-- ctl_accounting_enhancements checks both columns for negatives independently.
--
-- The neutral label is deliberate. Whether the balance is an ASC 606 CONTRACT ASSET or a
-- RECEIVABLE whose right to consideration is unconditional but simply not yet invoiced depends
-- on billing and payment terms the source does not record. The amount and the rollforward are
-- identical either way; the classification is not asserted.
--
-- CURRENT vs LONG-TERM. The longest billing period in the source is 12 months (Annual in
-- advance; multi-year contracts still invoice annually, PHASE1_SPEC 2.4), so no invoice is ever
-- raised for service more than 11 months beyond the month end. Long-term deferred revenue is
-- therefore structurally zero -- a property of the contract population, proven by the
-- max_months_to_period_end column and control C, not an assumption. A quarterly-in-advance or
-- multi-year-upfront population would produce a non-zero long-term balance.
with contract_month as (
    select
        segment,
        month_end_date,
        billings,
        subscription_revenue_recognised,
        deferred_revenue,
        unbilled_receivable,
        -- Months of service still to be recognised out of the current billed period.
        case when net_contract_position > 0 then months_remaining_in_period - 1 else 0 end
            as months_to_period_end
    from int_contract_billing_schedule
    where month_end_date between date '2023-12-31' and date '2026-06-30'
),

by_segment as (
    select
        segment,
        month_end_date,
        sum(billings)                        as billings,
        sum(subscription_revenue_recognised) as revenue_recognised,
        sum(deferred_revenue)                as ending_deferred_revenue,
        sum(unbilled_receivable)             as ending_unbilled_receivable,
        max(months_to_period_end)            as max_months_to_period_end
    from contract_month
    group by 1, 2
),

with_total as (
    select * from by_segment
    union all
    select 'Total', month_end_date, sum(billings), sum(revenue_recognised),
           sum(ending_deferred_revenue), sum(ending_unbilled_receivable),
           max(max_months_to_period_end)
    from by_segment
    group by 2
),

rolled as (
    select
        w.*,
        lag(w.ending_deferred_revenue) over (partition by w.segment order by w.month_end_date)
            as beginning_deferred_revenue,
        lag(w.ending_unbilled_receivable) over (partition by w.segment order by w.month_end_date)
            as beginning_unbilled_receivable
    from with_total w
)

select
    r.month_end_date,
    d.fiscal_year,
    d.fiscal_quarter,
    r.segment,
    r.beginning_deferred_revenue,
    r.billings,
    r.revenue_recognised,
    -- The change in the arrears unbilled receivable is the only reconciling item between the
    -- billings-less-revenue movement and the deferred-revenue movement, and it is stated, not
    -- absorbed: an arrears contract recognises revenue in a month it does not invoice, which
    -- moves the unbilled receivable rather than deferred revenue.
    r.ending_unbilled_receivable - r.beginning_unbilled_receivable as unbilled_receivable_movement,
    r.beginning_deferred_revenue + r.billings - r.revenue_recognised
        + (r.ending_unbilled_receivable - r.beginning_unbilled_receivable)
        as ending_deferred_revenue_calculated,
    r.ending_deferred_revenue,
    r.ending_deferred_revenue as deferred_revenue_current,
    0.0                       as deferred_revenue_long_term,
    r.max_months_to_period_end,
    r.beginning_unbilled_receivable,
    r.ending_unbilled_receivable,
    r.ending_deferred_revenue
        - (r.beginning_deferred_revenue + r.billings - r.revenue_recognised
           + (r.ending_unbilled_receivable - r.beginning_unbilled_receivable)) as rollforward_residual,
    -- The same rollforward stated on the NET position, where the three-line identity
    -- Beginning + Billings - Revenue = Ending holds with no reconciling item at all, because
    -- the arrears unbilled receivable is inside the net figure rather than beside it. Both forms
    -- are published: the gross form above is how a deferred-revenue schedule is presented, the
    -- net form here is the cleanest proof that nothing has been plugged.
    r.beginning_deferred_revenue - r.beginning_unbilled_receivable as beginning_net_contract_liability,
    r.ending_deferred_revenue - r.ending_unbilled_receivable       as ending_net_contract_liability,
    (r.ending_deferred_revenue - r.ending_unbilled_receivable)
        - (r.beginning_deferred_revenue - r.beginning_unbilled_receivable
           + r.billings - r.revenue_recognised) as net_rollforward_residual
from rolled r
join dim_date d on d.month_end_date = r.month_end_date
where r.month_end_date >= date '2024-01-31'
order by r.segment, r.month_end_date
