-- Shared FY2025 New Logo mix ratios, one row per segment, computed once and referenced wherever
-- the GTM capacity and pipeline layer needs a documented New-Logo share -- never re-derived ad
-- hoc in the report layer. Two DIFFERENT ratios, not to be confused with each other:
--
--   new_logo_share_of_bookings      WITHIN-segment: of a segment's own FY2025 credited CRM
--                                    bookings (New Logo + Expansion + Renewal Uplift ACV,
--                                    int_crm_closed_won), what share is New Logo. Used to convert
--                                    BLENDED sales capacity (fct_sales_capacity.
--                                    expected_productive_capacity, which credits all three deal
--                                    types against one quota -- see docs/gtm_finance.md) into a
--                                    New-Logo-only capacity measure, because comparing blended
--                                    capacity directly to a New-Logo-only ARR target is not
--                                    like-for-like.
--   share_of_company_new_logo_arr   BETWEEN-segment: of FY2025 company New Logo ARR
--                                    (fct_arr_movement, the ARR engine -- not CRM bookings, since
--                                    the target being allocated is itself an ARR figure), what
--                                    share landed in this segment. Sums to 1.0 across the three
--                                    segments. Used to allocate a company-level New Logo ARR
--                                    TARGET down to segments when no explicit segment target
--                                    exists in fact_budget or config/assumptions.yml -- neither
--                                    does; both were checked and confirmed absent
--                                    (docs/gtm_finance.md), so an arbitrary equal split is not
--                                    used either.
--
-- FY2025 for both: the same fully-closed, most-recent complete year the rest of this phase's
-- fixed-percentage assumptions are anchored to (int_gtm_cost_allocation's acquisition
-- percentage, fct_unit_economics' gross margin) -- entirely PRIOR to the forward periods this
-- ratio is applied to (the 30 June 2026 capacity snapshot, H2 2026 targets), so no forward
-- period's own outcome informs the ratio used to judge it. Applying a single FY2025-derived
-- ratio uniformly is also, by the same construction, applied retroactively to 2024 rows of
-- fct_sales_capacity as a modelling simplification -- documented as a limitation in
-- docs/gtm_finance.md, not asserted as historical fact for those earlier months.
with fy2025_bookings as (
    select
        segment,
        sum(case when deal_type = 'New Logo' then acv else 0 end) as new_logo_acv,
        sum(acv) as total_acv
    from int_crm_closed_won
    where actual_close_month between date '2025-01-31' and date '2025-12-31'
    group by 1
),

fy2025_arr_new_logo as (
    select segment, sum(movement_arr) as new_logo_arr
    from fct_arr_movement
    where movement_type = 'New Logo'
      and month_end_date between date '2025-01-31' and date '2025-12-31'
    group by 1
)

select
    b.segment,
    b.new_logo_acv as fy2025_new_logo_bookings_acv,
    b.total_acv as fy2025_total_bookings_acv,
    b.new_logo_acv / nullif(b.total_acv, 0) as new_logo_share_of_bookings,
    a.new_logo_arr as fy2025_new_logo_arr,
    a.new_logo_arr / sum(a.new_logo_arr) over () as share_of_company_new_logo_arr
from fy2025_bookings b
join fy2025_arr_new_logo a on a.segment = b.segment
order by b.segment
