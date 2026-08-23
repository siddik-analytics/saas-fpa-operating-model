-- Normalised CRM opportunity, one row per opportunity (stg_fact_crm_opportunity), with the
-- derived fields every downstream 05_gtm model needs: month-end date buckets (joined to
-- dim_date, not date_trunc'd in place, so every month key in this layer is a real
-- dim_date.month_end_date like the rest of the analytical layer), status flags and sales cycle
-- length. No filtering here -- open, closed-won and closed-lost opportunities are all in scope
-- for different questions, so keeping this unfiltered avoids re-deriving these flags five times.
select
    o.opportunity_id,
    o.account_id,
    o.segment,
    o.rep_id,
    o.created_date,
    dc.month_end_date as created_month,
    o.expected_close_date,
    dx.month_end_date as expected_close_month,
    o.actual_close_date,
    da.month_end_date as actual_close_month,
    o.stage,
    o.stage_probability,
    o.deal_type,
    o.contract_term_months,
    o.pipeline_value,
    o.acv,
    o.tcv,
    o.status,
    o.loss_reason,
    o.lead_source,
    o.provisioned_flag,
    (o.status = 'Won')  as is_won,
    (o.status = 'Lost') as is_lost,
    (o.status = 'Open') as is_open,
    (o.status = 'Won' and o.provisioned_flag) as is_provisioned_won,
    case when o.status = 'Won' then date_diff('day', o.created_date, o.actual_close_date) end
        as sales_cycle_days
from stg_fact_crm_opportunity o
join dim_date dc on dc.month_start_date = date_trunc('month', o.created_date)
left join dim_date dx on dx.month_start_date = date_trunc('month', o.expected_close_date)
left join dim_date da on da.month_start_date = date_trunc('month', o.actual_close_date)
