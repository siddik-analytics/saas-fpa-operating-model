-- Unit economics, one row per segment per actual quarter (plus a 'Blended' rollup), built from
-- the FY2025-anchored allocation in int_gtm_cost_allocation and the ARR engine's own New Logo
-- count (fct_arr_movement) -- never a separate CRM-based new-logo count, which would disagree
-- with the ARR engine by the same small margin fct_crm_arr_reconciliation already documents.
--
--   New-Customer CAC        = New-logo acquisition S&M in Q-1 / New logos acquired in Q
--   CAC per $1 New Logo ARR = New-logo acquisition S&M in Q  / New Logo ARR in Q
--   CAC Payback (months)    = CAC / (New-logo ARPA x Gross Margin % / 12)
--
-- Gross margin is COMPANY-LEVEL, computed once over FY2025 from fact_gl_actuals. The source
-- data carries no customer-segment dimension on revenue or COGS -- fact_gl_actuals' cost
-- centres are function-based, not customer-segment-based -- so a segment-level margin is not
-- supportable from this data and is not invented (PHASE1_SPEC governing constraint 3). Applied
-- uniformly across every segment's payback below; see docs/gtm_finance.md.
with quarters as (
    select fiscal_quarter, min(month_start_date) as quarter_start, max(month_end_date) as quarter_end
    from dim_date
    where is_actual
    group by 1
),

quarters_seq as (
    select *, row_number() over (order by quarter_start) as qn
    from quarters
),

quarter_with_prior as (
    select cur.fiscal_quarter, cur.quarter_start, cur.quarter_end, prev.fiscal_quarter as prior_fiscal_quarter
    from quarters_seq cur
    join quarters_seq prev on prev.qn = cur.qn - 1
),

segments as (
    select 'SMB' as segment union all select 'Mid-Market' union all select 'Enterprise'
),

new_logo_by_quarter_segment as (
    select d.fiscal_quarter, m.segment, count(*) as new_logos_count, sum(m.movement_arr) as new_logo_arr
    from fct_arr_movement m
    join dim_date d on d.month_end_date = m.month_end_date
    where m.movement_type = 'New Logo' and d.is_actual
    group by 1, 2
),

acquisition_cost_by_quarter_segment as (
    select d.fiscal_quarter, a.segment, sum(a.new_logo_allocated_cost) as new_logo_acquisition_sm
    from int_gtm_cost_allocation a
    join dim_date d on d.month_end_date = a.month_end_date
    group by 1, 2
),

gross_margin_inputs as (
    select
        sum(case when account_category in ('Subscription Revenue', 'Services Revenue') then -actual_amount else 0 end) as revenue,
        sum(case when account_category in ('Subscription COGS', 'Services COGS') then actual_amount else 0 end) as cogs
    from stg_fact_gl_actuals
    where month_end_date between date '2025-01-31' and date '2025-12-31'
),

gm as (
    select (revenue - cogs) / nullif(revenue, 0) as gross_margin_pct
    from gross_margin_inputs
),

segment_quarter as (
    select q.fiscal_quarter, q.prior_fiscal_quarter, s.segment
    from quarter_with_prior q
    cross join segments s
),

segment_rows as (
    select
        sq.fiscal_quarter,
        sq.segment,
        coalesce(nl.new_logos_count, 0) as new_logos_count,
        coalesce(nl.new_logo_arr, 0) as new_logo_arr,
        coalesce(nl.new_logo_arr, 0) / nullif(nl.new_logos_count, 0) as new_logo_arpa,
        ac_cur.new_logo_acquisition_sm as new_logo_acquisition_sm_current_quarter,
        ac_prior.new_logo_acquisition_sm as new_logo_acquisition_sm_prior_quarter,
        gm.gross_margin_pct
    from segment_quarter sq
    left join new_logo_by_quarter_segment nl on nl.fiscal_quarter = sq.fiscal_quarter and nl.segment = sq.segment
    left join acquisition_cost_by_quarter_segment ac_cur on ac_cur.fiscal_quarter = sq.fiscal_quarter and ac_cur.segment = sq.segment
    left join acquisition_cost_by_quarter_segment ac_prior on ac_prior.fiscal_quarter = sq.prior_fiscal_quarter and ac_prior.segment = sq.segment
    cross join gm
),

blended_rows as (
    select
        fiscal_quarter,
        'Blended' as segment,
        sum(new_logos_count) as new_logos_count,
        sum(new_logo_arr) as new_logo_arr,
        sum(new_logo_arr) / nullif(sum(new_logos_count), 0) as new_logo_arpa,
        sum(new_logo_acquisition_sm_current_quarter) as new_logo_acquisition_sm_current_quarter,
        sum(new_logo_acquisition_sm_prior_quarter) as new_logo_acquisition_sm_prior_quarter,
        max(gross_margin_pct) as gross_margin_pct
    from segment_rows
    group by 1
),

combined as (
    select * from segment_rows
    union all
    select * from blended_rows
)

select
    fiscal_quarter,
    segment,
    new_logos_count,
    new_logo_arr,
    new_logo_arpa,
    new_logo_acquisition_sm_current_quarter,
    new_logo_acquisition_sm_prior_quarter,
    gross_margin_pct,
    new_logo_acquisition_sm_prior_quarter / nullif(new_logos_count, 0) as cac,
    new_logo_acquisition_sm_current_quarter / nullif(new_logo_arr, 0) as cac_per_dollar_new_logo_arr,
    (new_logo_acquisition_sm_prior_quarter / nullif(new_logos_count, 0))
        / nullif(new_logo_arpa * gross_margin_pct / 12.0, 0) as cac_payback_months
from combined
order by fiscal_quarter, segment
