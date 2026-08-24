-- Subscription billings, by month and segment, with the recognised-revenue comparison that
-- keeps the four commercial metrics apart. Grain: month x segment (SMB / Mid-Market /
-- Enterprise / Total). Reporting window Jan-2024 .. Jun-2026, matching fact_gl_actuals.
--
-- BOOKINGS != BILLINGS != ARR != REVENUE (PHASE1_SPEC 8.6). This model deliberately reports
-- only ONE of the four. Bookings (TCV / ACV of executed contracts) live in fct_crm_bookings;
-- ARR (point-in-time annualised run-rate) lives in fct_arr_waterfall; recognised revenue is
-- carried here purely as the comparison that makes the deferral visible. Nothing in this model
-- collapses them into a single "revenue-ish" number.
--
-- WHY BILLINGS SWING SO HARD MONTH TO MONTH, and why billings growth is NOT headlined.
-- 89% of ARR sits on advance-billed contracts, so a month's billings are driven by which
-- contracts happen to hit a renewal anniversary that month, not by that month's trading. The
-- source's own renewal seasonality is binding (PHASE1_SPEC 2.5: ATR concentrates 28% in Q1 and
-- 31% in Q4), which puts a large, entirely mechanical spike into Dec / Jan / Mar. TTM billings
-- is therefore the only billings series this project treats as a growth metric, and even that
-- is reported alongside, never instead of, ARR.
--
-- Deferred revenue and the unbilled receivable are closing BALANCES, so they are summed at the
-- month, never over months. fct_deferred_revenue carries the rollforward that proves them.
with monthly as (
    select
        month_end_date,
        segment,
        sum(billings)                        as billings,
        sum(scheduled_billing)               as scheduled_billings,
        sum(proration_billing)               as proration_billings,
        sum(arrears_billing)                 as arrears_billings,
        sum(subscription_revenue_recognised) as subscription_revenue,
        sum(deferred_revenue)                as ending_deferred_revenue,
        sum(unbilled_receivable)             as ending_unbilled_receivable,
        -- In force means actually delivering service that month. A contract-month with a zero
        -- in-force rate is either the trailing month an arrears contract carries so its final
        -- invoice can land, or a gap in the subscription record, and is not counted.
        count(distinct case when in_force_monthly_rate > 0 then contract_id end) as contracts_in_force,
        count(distinct case when is_billing_anchor and bills_in_advance
                            then contract_id end) as contracts_invoiced_in_advance
    from int_contract_billing_schedule
    where month_end_date between date '2023-12-31' and date '2026-06-30'
    group by 1, 2
),

with_total as (
    select * from monthly
    union all
    select
        month_end_date, 'Total',
        sum(billings), sum(scheduled_billings), sum(proration_billings), sum(arrears_billings),
        sum(subscription_revenue), sum(ending_deferred_revenue), sum(ending_unbilled_receivable),
        sum(contracts_in_force), sum(contracts_invoiced_in_advance)
    from monthly
    group by 1
),

sequenced as (
    select
        w.*,
        row_number() over (partition by segment order by month_end_date) as rn
    from with_total w
),

ttm_windowed as (
    select
        s.*,
        case when s.rn >= 12
             then sum(s.billings) over (partition by s.segment order by s.month_end_date
                                        rows between 11 preceding and current row) end
            as ttm_billings,
        case when s.rn >= 12
             then sum(s.subscription_revenue) over (partition by s.segment order by s.month_end_date
                                                    rows between 11 preceding and current row) end
            as ttm_subscription_revenue,
        lag(s.billings, 12) over (partition by s.segment order by s.month_end_date)
            as billings_prior_year_month
    from sequenced s
)

select
    t.month_end_date,
    d.fiscal_year,
    d.fiscal_quarter,
    t.segment,
    t.billings,
    t.scheduled_billings,
    t.proration_billings,
    t.arrears_billings,
    t.subscription_revenue,
    t.billings - t.subscription_revenue as billings_less_revenue,
    t.ttm_billings,
    t.ttm_subscription_revenue,
    case when t.ttm_subscription_revenue > 0
         then t.ttm_billings / t.ttm_subscription_revenue end as ttm_billings_to_revenue,
    case when t.billings_prior_year_month > 0
         then t.billings / t.billings_prior_year_month - 1 end as billings_yoy_growth,
    t.ending_deferred_revenue,
    t.ending_unbilled_receivable,
    t.ending_deferred_revenue - t.ending_unbilled_receivable as ending_net_contract_liability,
    t.contracts_in_force,
    t.contracts_invoiced_in_advance
from ttm_windowed t
join dim_date d on d.month_end_date = t.month_end_date
where t.month_end_date >= date '2024-01-31'
order by t.segment, t.month_end_date
