-- Open CRM pipeline as of the reporting date (30 June 2026), one row per open opportunity.
-- Weighted pipeline = ACV x stage probability (PHASE1_SPEC 8.9); unweighted pipeline is ACV
-- itself. Both are exposed -- neither is assumed more accurate than the other
-- (docs/gtm_finance.md). Required pipeline (target / historical win rate) and coverage ratios
-- are computed in the report from this fact plus int_crm_opportunity_normalized's closed
-- population, since they mix two different grains (open pipeline here, closed history there).
select
    o.opportunity_id,
    o.account_id,
    o.segment,
    o.rep_id,
    o.created_date,
    o.created_month,
    o.expected_close_date,
    o.expected_close_month,
    d.fiscal_quarter as expected_close_quarter,
    o.stage,
    o.stage_probability,
    o.deal_type,
    o.pipeline_value,
    o.acv,
    o.acv * o.stage_probability as weighted_acv,
    o.lead_source
from int_crm_opportunity_normalized o
join dim_date d on d.month_end_date = o.expected_close_month
where o.is_open
order by o.expected_close_month, o.segment, o.opportunity_id
