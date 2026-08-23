-- Clean bookings view, one row per closed-won CRM opportunity (int_crm_closed_won). Bookings
-- (TCV of the executed contract) are kept explicitly distinct from ARR and from recognised
-- revenue (PHASE1_SPEC 8.6) by carrying both acv and tcv as separate columns rather than
-- collapsing them -- acv is the ARR the deal actually represents; tcv is the larger, full
-- contract-term figure on multi-year deals. Includes non-provisioned wins (provisioned_flag =
-- false); they are real bookings that never became ARR, which is exactly the distinction
-- fct_crm_arr_reconciliation exists to walk.
select
    opportunity_id,
    customer_id,
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
from int_crm_closed_won
order by actual_close_month, segment, opportunity_id
