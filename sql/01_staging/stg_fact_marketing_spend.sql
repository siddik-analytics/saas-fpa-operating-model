-- Staging: typed pass-through of fact_marketing_spend. No business logic.
--
-- Channel-level detail behind the demand-generation cost centre (CC-1100), which ties to
-- accounts 6100, 6110 and 6120 in fact_gl_actuals (docs/data_dictionary.md). The GL rollup, not
-- this table, drives the CAC allocation in int_gtm_cost_allocation, to avoid double counting;
-- this model exists for channel-level reporting context only.
select
    cast(month_end_date as date) as month_end_date,
    channel,
    cast(spend as decimal(18, 2)) as spend,
    opportunities_created
from raw_fact_marketing_spend
