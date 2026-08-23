-- New-logo acquisition cost allocation (PHASE1_SPEC 8.5), one row per Sales & Marketing cost
-- centre x actual month x segment. Every dollar fact_gl_actuals posts to a Sales & Marketing
-- cost centre is split across the three segments and then across a new-logo acquisition
-- percentage; fct_unit_economics sums new_logo_allocated_cost to build the CAC numerator.
--
-- Deviation from a literal reading of PHASE1_SPEC 8.5, recorded here because the specification
-- is frozen and this is a departure from it (same convention as docs/generation_methodology.md
-- section 8). PHASE1_SPEC 8.5's own allocation table assumes two rep populations -- "new-logo
-- AEs" (100% acquisition) and "expansion AEs" (0%) -- but dim_sales_rep and
-- config/chart_of_accounts.yml carry only ONE blended AE per segment cost centre
-- (CC-1000/1010/1020), each commissioned on new-logo, expansion AND renewal-uplift ACV
-- (dim_sales_rep.commission_rate_new / _expansion; config/assumptions.yml
-- sales_reps.commission_rate_renewal_uplift). There is no dedicated expansion-selling cost
-- centre in this dataset to exclude. The most defensible substitute available from the source
-- data: the AE cost centres, and by the same "AE headcount split" logic PHASE1_SPEC already
-- applies to Sales Ops and leadership, the shared pools (CC-1030/1040/1050/1060/1100) too, are
-- allocated to acquisition using the realised New Logo share of FY2025 closed-won ACV credited
-- to that population's reps (int_crm_closed_won) -- a fixed, data-derived percentage, not a
-- free parameter, and consistent with PHASE1_SPEC's own single resolved ~49% company figure
-- rather than a period-varying one. See docs/gtm_finance.md.
--
-- Two independent allocation axes:
--   segment_cost_share_pct  which segment a shared cost pool's dollars belong to. CC-1000/1010/
--                           1020 map 1:1 to their own segment. The shared pools
--                           (CC-1030/1040/1050/1060/1100) are split by each segment's share of
--                           ACTIVE AE HEADCOUNT at 31 Dec 2025 (dim_sales_rep) -- the literal
--                           "AE headcount split" PHASE1_SPEC 8.5 names.
--   new_logo_pct            what share of that segment's dollars is acquisition (vs. expansion /
--                           renewal-uplift selling, or excluded entirely). SDR and demand
--                           generation are 100% per PHASE1_SPEC 8.5; brand/content (CC-1110) and
--                           Customer Success (CC-1200) are 0%; everything else uses the FY2025
--                           bookings-mix percentage described above.
with fy2025_bookings_mix as (
    select
        segment,
        sum(case when deal_type = 'New Logo' then acv else 0 end) as new_logo_acv,
        sum(acv) as total_acv
    from int_crm_closed_won
    where actual_close_month between date '2025-01-31' and date '2025-12-31'
    group by 1
),

segment_new_logo_pct as (
    select segment, new_logo_acv / nullif(total_acv, 0) as new_logo_pct
    from fy2025_bookings_mix
),

blended_new_logo_pct as (
    select sum(new_logo_acv) / nullif(sum(total_acv), 0) as new_logo_pct
    from fy2025_bookings_mix
),

ae_headcount_by_segment as (
    select segment, count(*) as active_aes
    from dim_sales_rep
    where hire_date <= date '2025-12-31'
      and (termination_date is null or termination_date > date '2025-12-31')
    group by 1
),

segment_headcount_share as (
    select segment, active_aes::double / sum(active_aes) over () as share_pct
    from ae_headcount_by_segment
),

segments as (
    select 'SMB' as segment union all select 'Mid-Market' union all select 'Enterprise'
),

gl_sm as (
    select month_end_date, cost_center, department, sum(actual_amount) as total_cost
    from stg_fact_gl_actuals
    where account_category = 'Sales & Marketing'
    group by 1, 2, 3
),

allocated as (
    select
        g.month_end_date,
        g.cost_center,
        g.department,
        g.total_cost,
        s.segment,
        case
            when g.cost_center = 'CC-1000' then (case when s.segment = 'SMB' then 1.0 else 0.0 end)
            when g.cost_center = 'CC-1010' then (case when s.segment = 'Mid-Market' then 1.0 else 0.0 end)
            when g.cost_center = 'CC-1020' then (case when s.segment = 'Enterprise' then 1.0 else 0.0 end)
            else hc.share_pct
        end as segment_cost_share_pct,
        case
            when g.cost_center = 'CC-1000' then (select new_logo_pct from segment_new_logo_pct where segment = 'SMB')
            when g.cost_center = 'CC-1010' then (select new_logo_pct from segment_new_logo_pct where segment = 'Mid-Market')
            when g.cost_center = 'CC-1020' then (select new_logo_pct from segment_new_logo_pct where segment = 'Enterprise')
            when g.cost_center = 'CC-1030' then 1.00
            when g.cost_center = 'CC-1040' then (select new_logo_pct from blended_new_logo_pct)
            when g.cost_center = 'CC-1050' then (select new_logo_pct from blended_new_logo_pct)
            when g.cost_center = 'CC-1060' then (select new_logo_pct from blended_new_logo_pct)
            when g.cost_center = 'CC-1100' then 1.00
            when g.cost_center = 'CC-1110' then 0.00
            when g.cost_center = 'CC-1200' then 0.00
            else 0.00
        end as new_logo_pct,
        case
            when g.cost_center = 'CC-1000' then 'New Logo AE, SMB -- 100% to own segment; acquisition % = FY2025 SMB AE bookings mix'
            when g.cost_center = 'CC-1010' then 'New Logo AE, Mid-Market -- 100% to own segment; acquisition % = FY2025 Mid-Market AE bookings mix'
            when g.cost_center = 'CC-1020' then 'New Logo AE, Enterprise -- 100% to own segment; acquisition % = FY2025 Enterprise AE bookings mix'
            when g.cost_center = 'CC-1030' then 'SDR -- 100% acquisition (PHASE1_SPEC 8.5); split across segments by FY2025 active AE headcount'
            when g.cost_center in ('CC-1040', 'CC-1050', 'CC-1060') then 'Sales Ops / Solutions Engineering / Leadership -- split across segments by FY2025 active AE headcount; acquisition % = blended FY2025 AE bookings mix'
            when g.cost_center = 'CC-1100' then 'Demand generation -- 100% acquisition (PHASE1_SPEC 8.5); split across segments by FY2025 active AE headcount'
            when g.cost_center = 'CC-1110' then 'Product Marketing (brand / content) -- 0% acquisition (PHASE1_SPEC 8.5)'
            when g.cost_center = 'CC-1200' then 'Customer Success -- 0% acquisition (PHASE1_SPEC 8.5)'
            else '0% -- not a GTM acquisition cost pool'
        end as allocation_basis
    from gl_sm g
    cross join segments s
    left join segment_headcount_share hc on hc.segment = s.segment
)

select
    month_end_date,
    cost_center,
    department,
    segment,
    total_cost,
    segment_cost_share_pct,
    total_cost * segment_cost_share_pct as segment_cost,
    allocation_basis,
    new_logo_pct,
    total_cost * segment_cost_share_pct * new_logo_pct as new_logo_allocated_cost
from allocated
order by month_end_date, cost_center, segment
