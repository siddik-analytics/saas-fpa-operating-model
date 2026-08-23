-- Staging: typed pass-through of fact_crm_opportunity. No business logic.
--
-- The CRM is deliberately not a clean mirror of ARR (docs/data_dictionary.md,
-- docs/generation_methodology.md section 7) -- account_id is a real customer_id only for a
-- provisioned win; it is a prospect id on every loss and on the ~3% of closed-won deals that
-- never activate. acv is the ARR the opportunity actually represents (first-year value on a new
-- logo, the ARR an expansion added, the price rise on a renewal uplift), not the value of the
-- underlying contract -- tcv is the separate, larger figure on multi-year deals.
select
    opportunity_id,
    account_id,
    segment,
    rep_id,
    cast(created_date as date)        as created_date,
    cast(expected_close_date as date) as expected_close_date,
    cast(actual_close_date as date)   as actual_close_date,
    stage,
    cast(stage_probability as decimal(9, 4)) as stage_probability,
    deal_type,
    contract_term_months,
    cast(pipeline_value as decimal(18, 2)) as pipeline_value,
    cast(acv as decimal(18, 2))            as acv,
    cast(tcv as decimal(18, 2))            as tcv,
    status,
    loss_reason,
    lead_source,
    cast(provisioned_flag as boolean) as provisioned_flag
from raw_fact_crm_opportunity
