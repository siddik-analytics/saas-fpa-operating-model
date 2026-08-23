-- Staging: typed pass-through of dim_sales_rep. No business logic.
--
-- Loaded from Phase 5 onward for the GTM capacity and pipeline layer. Every row here is a
-- quota-carrying account executive -- dim_sales_rep is scoped to AEs only. SDRs, Solutions
-- Engineers, Sales Ops and Sales Leadership appear in dim_employee, not here
-- (docs/gtm_finance.md).
select
    rep_id,
    rep_name,
    segment,
    territory,
    cast(hire_date as date)        as hire_date,
    cast(termination_date as date) as termination_date,
    cast(annual_quota as decimal(18, 2))             as annual_quota,
    ramp_profile_id,
    cast(commission_rate_new as decimal(9, 4))       as commission_rate_new,
    cast(commission_rate_expansion as decimal(9, 4)) as commission_rate_expansion,
    manager_id
from raw_dim_sales_rep
