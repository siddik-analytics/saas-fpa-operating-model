-- Customer-grain historical renewal events -- the resolved counterpart to fct_renewal_base.
-- One row per non-monthly contract whose own renewal decision has already happened
-- (renewal_status in 'Renewed', 'Churned', 'Early Termination'). Month-to-month contracts have
-- no anniversary and no renewal_date (docs/data_dictionary.md) and never appear here.
--
-- Pre- and post-renewal ARR are read from int_arr_customer_month (the ARR engine, PHASE1_SPEC
-- 8.2), never from fact_contract.net_acv: net_acv is fixed at contract signing and does not pick
-- up mid-term seat or module growth that has since become part of the customer's real ARR --
-- see docs/retention_renewals.md for the size of that gap.
--
-- Renewed: the "outcome month" is the first month fact_subscription_monthly carries the
-- SUCCESSOR contract_id for that customer. Empirically (see docs/retention_renewals.md) this is
-- always the calendar month after the successor contract's own start_date, because the state
-- table assigns a whole month to whichever contract governed most of it, not strictly whichever
-- was in force at month end. int_arr_customer_month's beg_arr at that month is the pre-renewal
-- ARR; end_arr is the realised outcome.
--
-- Churned / Early Termination: there is no successor row, so the outcome month is instead the
-- customer's own churn event in int_arr_customer_month (end_arr drops to zero from a positive
-- beg_arr) -- the first such month on or after this contract's end_date, which anchors correctly
-- to this specific contract even for a churn-and-return customer whose full history contains
-- more than one churn event.
with resolved as (
    select
        c.contract_id,
        c.customer_id,
        cu.segment,
        c.contract_type,
        c.renewal_date,
        c.end_date,
        c.renewal_status
    from stg_fact_contract c
    join dim_customer cu on cu.customer_id = c.customer_id
    where c.renewal_status in ('Renewed', 'Churned', 'Early Termination')
      and c.contract_type <> 'monthly'
),

successor as (
    select
        predecessor_contract_id as contract_id,
        contract_id as successor_contract_id,
        uplift_pct_at_renewal as successor_uplift_pct
    from stg_fact_contract
    where predecessor_contract_id is not null
),

renewed_outcome_month as (
    select s.contract_id, min(sub.month_end_date) as outcome_month
    from successor s
    join stg_fact_subscription_monthly sub
        on sub.contract_id = s.successor_contract_id
    group by 1
),

churn_outcome_month as (
    select
        r.contract_id,
        (
            select min(m.month_end_date)
            from int_arr_customer_month m
            where m.customer_id = r.customer_id
              and m.beg_arr > 0
              and m.end_arr = 0
              and m.month_end_date >= r.end_date
        ) as outcome_month
    from resolved r
    where r.renewal_status in ('Churned', 'Early Termination')
),

outcome_month as (
    select contract_id, outcome_month from renewed_outcome_month
    union all
    select contract_id, outcome_month from churn_outcome_month
)

select
    r.contract_id,
    r.customer_id,
    r.segment,
    r.contract_type,
    r.renewal_date,
    r.end_date as contract_end_date,
    r.renewal_status,
    suc.successor_contract_id,
    suc.successor_uplift_pct,
    om.outcome_month,
    m.beg_arr as pre_renewal_arr,
    m.end_arr as post_renewal_arr
from resolved r
join outcome_month om on om.contract_id = r.contract_id
left join successor suc on suc.contract_id = r.contract_id
join int_arr_customer_month m
    on m.customer_id = r.customer_id
   and m.month_end_date = om.outcome_month
