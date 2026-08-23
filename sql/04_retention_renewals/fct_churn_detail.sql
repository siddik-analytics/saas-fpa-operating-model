-- Every churn event, all contract types (PHASE1_SPEC section 11) -- including month-to-month
-- customers, who have no renewal_date and never appear in int_contract_renewal_event,
-- fct_renewal_base or fct_renewal_outcomes (docs/data_dictionary.md).
--
-- The churning contract is identified deterministically, not by nearest-date heuristics:
-- fact_subscription_monthly records "the contract in force at month end" for every month a
-- customer was live (docs/data_dictionary.md), so the contract active in the customer's LAST
-- month with positive ARR is the one that did not renew. This also correctly anchors a
-- churn-and-return customer's earlier churn event to the contract that actually churned, rather
-- than to whichever contract happens to be nearest in time.
--
-- No qualitative churn reason is invented: the source data does not carry one, so none is added
-- here (PHASE1_SPEC section 11, "do not invent qualitative churn reasons if they do not exist").
with churn_events as (
    select
        m.customer_id,
        m.segment,
        m.month_end_date as churn_month,
        m.beg_arr as prior_arr
    from int_arr_customer_month m
    where m.beg_arr > 0 and m.end_arr = 0
),

last_active_month as (
    select
        ce.customer_id,
        ce.segment,
        ce.churn_month,
        ce.prior_arr,
        (
            select max(d.month_end_date)
            from dim_date d
            where d.month_end_date < ce.churn_month
        ) as prior_month
    from churn_events ce
),

churning_contract as (
    select distinct
        lam.customer_id,
        lam.segment,
        lam.churn_month,
        lam.prior_arr,
        sub.contract_id
    from last_active_month lam
    join stg_fact_subscription_monthly sub
        on sub.customer_id = lam.customer_id
       and sub.month_end_date = lam.prior_month
)

select
    cc.customer_id,
    cc.segment,
    cu.acquisition_date,
    year(cu.acquisition_date)::varchar || 'Q' || (((month(cu.acquisition_date) - 1) // 3) + 1)::varchar
        as acquisition_quarter,
    cc.churn_month,
    date_diff('month', cu.acquisition_date, cc.churn_month) as tenure_months,
    cc.prior_arr,
    cc.contract_id,
    c.contract_type,
    c.end_date as contract_end_date,
    c.renewal_date,
    c.renewal_status,
    c.renewal_status = 'Early Termination' as is_early_termination
from churning_contract cc
join dim_customer cu on cu.customer_id = cc.customer_id
join stg_fact_contract c on c.contract_id = cc.contract_id
order by churn_month, segment, customer_id
