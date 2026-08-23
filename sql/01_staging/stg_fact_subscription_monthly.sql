-- Staging: typed pass-through of fact_subscription_monthly. No business logic.
--
-- This table stores state only (customer x product x month). It is sparse: a customer has
-- rows only in months it was live, and a churned customer has no rows afterward. Every
-- downstream model that lags this to classify movement must build a dense spine first
-- (see int_arr_customer_month and int_arr_customer_product_month) -- see docs/data_dictionary.md.
select
    customer_id,
    product_id,
    contract_id,
    cast(month_end_date as date) as month_end_date,
    seats,
    cast(mrr as decimal(18, 2)) as mrr,
    cast(arr as decimal(18, 2)) as arr
from raw_fact_subscription_monthly
