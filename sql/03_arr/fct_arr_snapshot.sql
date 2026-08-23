-- Point-in-time customer ARR snapshot. One row per customer-month. A convenience read layer
-- over int_arr_customer_month for reporting and for fct_arr_concentration, so consumers do
-- not need to know that beg_arr/end_arr live on the movement-engine intermediate model.
select
    customer_id,
    segment,
    month_end_date,
    end_arr as arr,
    seats,
    end_arr > 0 as is_active
from int_arr_customer_month
