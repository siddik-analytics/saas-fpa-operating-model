-- Contract-level MONTHLY RATABLE ANALYTICAL billing and revenue schedule. Grain: contract x
-- month, over each contract's COMMITTED life (start_date .. end_date), not just the months the
-- subscription extract happens to cover. This is the single engine behind fct_billings,
-- fct_deferred_revenue and fct_revenue_accounting_reconciliation.
--
-- WHAT THIS IS, AND WHAT IT IS NOT. Revenue here is the contract's OBSERVED MONTHLY IN-FORCE MRR,
-- recognised at month grain. It is materially more contract-granular than the source ledger's
-- lagged-ARR management convention, because it is built per contract from that contract's own
-- rate and cadence rather than from a company-level ARR blend. It is NOT an ASC 606 subledger:
-- there is no daily proration of the service period for mid-month commencement or termination,
-- no invoice dates (only invoice months), and no standalone-selling-price allocation across
-- performance obligations. Those are limits of the source, not choices, and they are documented
-- in docs/accounting_enhancements.md rather than papered over.
--
-- BINDING SOURCE MECHANICS (PHASE1_SPEC 2.4, 2.5, 8.6; docs/accounting_enhancements.md):
--
--   Billing cadence is a CONTRACT ATTRIBUTE, never inferred from segment and never randomised:
--   fact_contract.billing_frequency is populated on every contract and maps to a period length
--   of 1 / 3 / 12 months.
--
--   Advance-billed contracts (Quarterly in advance, Annual in advance) invoice at each period
--   ANCHOR month -- the start month, then every `step` months -- for the monthly rate in force
--   at the anchor multiplied by the period length. PHASE1_SPEC 2.5 is binding that "mid-term
--   expansion is prorated and co-terminous": an increase in the in-force rate part-way through
--   an already-invoiced period raises a PRORATED catch-up invoice for the rate delta times the
--   months remaining in that period. Those two components together make total billings over a
--   billing period identically equal to total revenue recognised over the same period, so the
--   deferred-revenue balance self-liquidates to exactly zero at the end of every contract with
--   NO plug and NO balancing line. ctl_accounting_enhancements proves this contract by contract.
--
--   Arrears-billed contracts (Monthly in arrears -- month-to-month agreements, PHASE1_SPEC 2.4)
--   invoice in the month AFTER the service month, which is what "in arrears" means. Service
--   delivered but not yet billed is an UNBILLED RECEIVABLE, NOT negative deferred revenue. The
--   two are carried as separate non-negative columns here and are never netted into a single
--   figure that could hide a negative balance.
--
--   The label stays "unbilled receivable" deliberately. Whether such a balance is an ASC 606
--   CONTRACT ASSET (a right to consideration conditional on something other than the passage of
--   time) or simply a RECEIVABLE not yet invoiced turns on the contract's billing and payment
--   terms, and the source carries no invoicing or legal-right detail to decide it either way.
--   The balance and its rollforward are unaffected by that classification; asserting one would
--   be claiming a balance-sheet presentation the source cannot support.
--
-- THE IN-FORCE MONTHLY RATE, and the two window conventions it needs.
--   fact_subscription_monthly observes MRR at contract x month for 2023-12 .. 2026-06 only.
--   Inside that window the rate IS the observed MRR (zero in a month the contract carries no
--   subscription row), which makes recognised revenue here tie to the Phase 3 ARR engine's own
--   basis exactly rather than approximately. Outside the window the source carries no rate at
--   all, so the nearest observed month's rate is carried backward (for committed months before
--   Dec-2023) and forward (for committed months after Jun-2026). Both edges are analytical
--   conventions, are documented as such, and exist only to close the rollforward -- neither is
--   reported as revenue, because only in-window months are reported.
--
-- ELIGIBILITY. A contract enters the schedule only if it has at least one observed subscription
-- month in the window. 42 of 2,255 contracts (1.9%) do not: every one is a renewal with service
-- starting on or after 2 Jun 2026, whose service months fall outside the extract. Including
-- their first invoice without the matching revenue would manufacture deferred revenue that no
-- recognised revenue ever unwinds, so they are excluded and disclosed rather than plugged.
with window_bounds as (
    select date '2023-12-31' as window_start, date '2026-06-30' as window_end
),

contract_month_mrr as (
    -- Subscription state rolled from customer x product x month up to contract x month.
    select contract_id, month_end_date, sum(mrr)::double as mrr
    from stg_fact_subscription_monthly
    group by 1, 2
),

observed_edges as (
    select
        contract_id,
        min(month_end_date) as first_observed_month,
        max(month_end_date) as last_observed_month,
        arg_min(mrr, month_end_date) as first_observed_mrr,
        arg_max(mrr, month_end_date) as last_observed_mrr
    from contract_month_mrr
    group by 1
),

eligible_contract as (
    select
        c.contract_id,
        c.customer_id,
        cu.segment,
        c.contract_type,
        c.billing_frequency,
        c.term_months,
        c.start_date,
        c.end_date,
        c.net_acv::double as net_acv,
        case c.billing_frequency
            when 'Monthly in arrears'   then 1
            when 'Quarterly in advance' then 3
            when 'Annual in advance'    then 12
        end as billing_period_months,
        (c.billing_frequency <> 'Monthly in arrears') as bills_in_advance,
        (date_diff('month', date_trunc('month', c.start_date), date_trunc('month', c.end_date)) + 1)
            as committed_life_months,
        e.first_observed_mrr,
        e.last_observed_mrr,
        e.first_observed_month,
        e.last_observed_month
    from stg_fact_contract c
    join observed_edges e on e.contract_id = c.contract_id
    join dim_customer cu on cu.customer_id = c.customer_id
    where c.end_date >= c.start_date
),

spine as (
    -- One row per committed contract-month. Arrears contracts get one extra trailing month so
    -- the final in-arrears invoice, which is raised the month after the last service month,
    -- has somewhere to land; that extra month carries a zero in-force rate and zero revenue.
    select
        c.*,
        g.k::integer as period_offset,
        last_day(date_trunc('month', c.start_date) + to_months(g.k::integer)) as month_end_date
    from eligible_contract c
    cross join generate_series(0, 130) g(k)
    where g.k < c.committed_life_months + (case when c.bills_in_advance then 0 else 1 end)
),

rated as (
    select
        s.*,
        w.window_start,
        w.window_end,
        case
            -- The trailing month an arrears contract carries so its final invoice has somewhere
            -- to land is past the committed term: no service, so no rate and no revenue.
            when s.period_offset >= s.committed_life_months then 0.0
            when s.month_end_date between w.window_start and w.window_end
                then coalesce(m.mrr, 0.0)
            when s.month_end_date < w.window_start then s.first_observed_mrr
            else s.last_observed_mrr
        end as in_force_monthly_rate
    from spine s
    cross join window_bounds w
    left join contract_month_mrr m
        on m.contract_id = s.contract_id and m.month_end_date = s.month_end_date
),

periodised as (
    select
        r.*,
        (r.period_offset // r.billing_period_months) * r.billing_period_months as period_start_offset,
        least(
            r.billing_period_months,
            greatest(r.committed_life_months
                     - (r.period_offset // r.billing_period_months) * r.billing_period_months, 0)
        ) as billing_period_length,
        lag(r.in_force_monthly_rate) over (partition by r.contract_id order by r.period_offset)
            as prior_monthly_rate
    from rated r
),

billed as (
    select
        p.*,
        (p.period_offset = p.period_start_offset) as is_billing_anchor,
        p.period_start_offset + p.billing_period_length - p.period_offset
            as months_remaining_in_period,
        coalesce(p.in_force_monthly_rate - p.prior_monthly_rate, 0.0) as monthly_rate_delta,
        -- Advance: the whole period invoiced at the anchor.
        case when p.bills_in_advance and p.period_offset = p.period_start_offset
             then p.in_force_monthly_rate * p.billing_period_length else 0.0 end
            as scheduled_billing,
        -- Advance: co-terminous prorated catch-up for a mid-period rate change.
        case when p.bills_in_advance and p.period_offset <> p.period_start_offset
             then coalesce(p.in_force_monthly_rate - p.prior_monthly_rate, 0.0)
                  * (p.period_start_offset + p.billing_period_length - p.period_offset)
             else 0.0 end
            as proration_billing,
        -- Arrears: the prior month's service, invoiced this month.
        case when not p.bills_in_advance then coalesce(p.prior_monthly_rate, 0.0) else 0.0 end
            as arrears_billing
    from periodised p
),

positioned as (
    select
        b.*,
        b.scheduled_billing + b.proration_billing + b.arrears_billing as billings,
        b.in_force_monthly_rate as subscription_revenue_recognised,
        sum(b.scheduled_billing + b.proration_billing + b.arrears_billing - b.in_force_monthly_rate)
            over (partition by b.contract_id order by b.period_offset
                  rows between unbounded preceding and current row)
            as net_contract_position
    from billed b
)

select
    contract_id,
    customer_id,
    segment,
    contract_type,
    billing_frequency,
    bills_in_advance,
    billing_period_months,
    term_months,
    start_date,
    end_date,
    month_end_date,
    period_offset,
    period_start_offset,
    billing_period_length,
    months_remaining_in_period,
    is_billing_anchor,
    in_force_monthly_rate,
    -- The contract's own stated annualised value, carried so a reader can compare it to the
    -- in-force rate x 12. They diverge on any contract that expanded mid-term: net_acv is the
    -- value at signature and does not move, which is exactly why billings are built from the
    -- in-force rate and the proration rule rather than from net_acv.
    net_acv,
    monthly_rate_delta,
    scheduled_billing,
    proration_billing,
    arrears_billing,
    billings,
    subscription_revenue_recognised,
    net_contract_position,
    -- Deferred revenue and the unbilled receivable, presented separately and both non-negative.
    greatest(net_contract_position, 0.0)  as deferred_revenue,
    greatest(-net_contract_position, 0.0) as unbilled_receivable,
    (month_end_date between window_start and window_end) as is_in_observation_window,
    (month_end_date between date '2024-01-31' and date '2026-06-30') as is_in_reporting_window
from positioned
order by contract_id, month_end_date
