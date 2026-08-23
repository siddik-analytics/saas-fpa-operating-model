-- Available-to-Renew (ATR): contracts currently in force whose own renewal date is still ahead
-- of the reporting date (PHASE1_SPEC 8.3). Grain: one row per contract with a future
-- renewal_date. Month-to-month contracts never appear here -- they have no anniversary and no
-- renewal_date (docs/data_dictionary.md).
--
-- ATR = the ARR that will come up for a renewal decision in a given future month, measured at
-- the ARR actually in force today -- not fact_contract.net_acv, which is fixed at signing or
-- last repricing and does not pick up mid-term seat or module growth that has since become part
-- of the customer's real ARR. Across the contracts eligible here, net_acv understates actual
-- ARR by roughly 13% in aggregate; see docs/retention_renewals.md.
--
-- Phase 4 does not forecast ARR growth between the reporting date and a future renewal date --
-- that is Phase 6 scope. atr_arr is the customer's actual ARR as of the last actual reporting
-- month (30 June 2026), carried forward unchanged as the best available estimate of "ARR in
-- force immediately before renewal" for a renewal that has not happened yet. This is a modelling
-- assumption, documented rather than silently embedded.
--
-- A handful of multi-year contracts (signed years ago, term up to 36 months) have a renewal_date
-- past 2027-12-31, the end of dim_date's calendar spine -- the join to dim_date below excludes
-- them rather than erroring. All renewals due within the required forward 12-month window are
-- well inside dim_date's range regardless; this only drops renewals due beyond it, documented in
-- docs/retention_renewals.md rather than silently dropped.
with report_month as (
    select max(month_end_date) as month_end_date from dim_date where is_actual
),

current_arr as (
    select m.customer_id, m.end_arr as atr_arr
    from int_arr_customer_month m, report_month r
    where m.month_end_date = r.month_end_date
)

select
    c.contract_id,
    c.customer_id,
    cu.segment,
    c.contract_type,
    c.renewal_date,
    d.month_end_date as renewal_month,
    ca.atr_arr,
    c.net_acv as contract_net_acv,
    date_diff('month', r.month_end_date, d.month_end_date) as months_to_renewal
from stg_fact_contract c
join dim_customer cu on cu.customer_id = c.customer_id
join current_arr ca on ca.customer_id = c.customer_id
join dim_date d on d.month_start_date = date_trunc('month', c.renewal_date)
cross join report_month r
where c.renewal_status = 'Active'
  and c.contract_type <> 'monthly'
  and c.renewal_date > r.month_end_date
order by renewal_month, segment, contract_id
