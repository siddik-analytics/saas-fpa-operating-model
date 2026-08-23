-- Customer-grain ARR movement -- the engine. One row per customer-month, one movement type
-- per row (PHASE1_SPEC 8.2, binding). This is the grain that feeds fct_arr_waterfall and,
-- in later phases, retention, NRR and GRR.
--
-- The six rules, applied in order against beg_arr = LAG(customer ARR) and
-- had_positive_arr_before = "customer ever had ARR > 0 strictly before this month":
--   beg=0,  end>0,  never positive before  -> New Logo
--   beg=0,  end>0,  positive before        -> Reactivation
--   beg>0,  end=0                          -> Churn
--   end > beg > 0                          -> Expansion
--   0 < end < beg                          -> Contraction
--   end = beg                              -> No Change
select
    customer_id,
    segment,
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
from int_arr_customer_month
