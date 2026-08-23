-- Closed-won CRM opportunities only -- the population fct_crm_bookings, the CRM-to-ARR bridge
-- and the win-rate / CAC calculations all read. Kept separate from
-- int_crm_opportunity_normalized so every downstream model filters "closed-won" the same way
-- instead of repeating `status = 'Won'`.
--
-- customer_id is populated only for a provisioned win -- account_id is a real customer_id only
-- then (docs/data_dictionary.md); it is null for the ~3% of closed-won deals that never
-- activate, so a left join against fct_arr_movement on customer_id correctly finds no match for
-- them rather than accidentally matching a prospect id that happens to collide with a real one.
select
    opportunity_id,
    case when provisioned_flag then account_id end as customer_id,
    account_id,
    segment,
    rep_id,
    deal_type,
    contract_term_months,
    created_date,
    actual_close_date,
    actual_close_month,
    acv,
    tcv,
    provisioned_flag,
    sales_cycle_days
from int_crm_opportunity_normalized
where is_won
