-- Product-grain ARR movement -- a SEPARATE model from fct_arr_movement (PHASE1_SPEC 8.2,
-- binding). Classified at customer x product grain using the same six rules, over the dense
-- product-level spine in int_arr_customer_product_month.
--
-- Movement categories here do NOT aggregate to the customer-grain waterfall and are NOT used
-- for NRR, GRR or any retention metric. A customer who moves $30k of ARR from Helio Dispatch
-- to Helio Core in one month shows a $30k contraction on Dispatch and a $30k expansion on Core
-- here -- and correctly nothing at customer grain in fct_arr_movement, where the same customer
-- nets to No Change. Total ARR ties between the two models in every month
-- (ctl_arr_reconciliation, product_customer_tie); movement categories do not, by design.
--
-- Answers product-mix questions -- which modules drive expansion, which are being dropped --
-- and nothing else. Never join this to retention or the headline waterfall.
select
    customer_id,
    product_id,
    month_end_date,
    beg_arr,
    end_arr,
    end_arr - beg_arr as movement_arr,
    case
        when beg_arr = 0 and end_arr > 0 and had_positive_arr_before = 0 then 'New Logo'
        when beg_arr = 0 and end_arr > 0 and had_positive_arr_before = 1 then 'Reactivation'
        when beg_arr > 0 and end_arr = 0                                 then 'Churn'
        when end_arr > beg_arr and beg_arr > 0                           then 'Expansion'
        when end_arr < beg_arr and end_arr > 0                           then 'Contraction'
        when end_arr = beg_arr                                           then 'No Change'
    end as movement_type
from int_arr_customer_product_month
