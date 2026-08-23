-- Staging: typed pass-through of fact_contract. No business logic.
--
-- Loaded from Phase 4 onward for the renewal base and renewal outcomes (docs/retention_renewals.md).
-- renewal_date is null for month-to-month contracts, which have no anniversary and never appear
-- in a renewal base (docs/data_dictionary.md).
select
    contract_id,
    customer_id,
    contract_type,
    term_months,
    cast(start_date as date)    as start_date,
    cast(end_date as date)      as end_date,
    cast(renewal_date as date)  as renewal_date,
    billing_frequency,
    cast(list_acv as decimal(18, 2))            as list_acv,
    cast(discount_pct as decimal(9, 4))         as discount_pct,
    cast(net_acv as decimal(18, 2))             as net_acv,
    cast(tcv as decimal(18, 2))                 as tcv,
    renewal_status,
    predecessor_contract_id,
    cast(uplift_pct_at_renewal as decimal(9, 4)) as uplift_pct_at_renewal
from raw_fact_contract
