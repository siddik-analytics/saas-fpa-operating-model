-- Staging: typed pass-through of dim_customer. No business logic.
select
    customer_id,
    customer_name,
    segment,
    employee_count,
    region,
    cast(acquisition_date as date)   as acquisition_date,
    acquisition_channel,
    initial_contract_type,
    journey_archetype,
    account_owner_rep_id,
    csm_id,
    customer_status,
    cast(churn_date as date)         as churn_date,
    cast(first_arr as decimal(18, 2)) as first_arr
from raw_dim_customer
