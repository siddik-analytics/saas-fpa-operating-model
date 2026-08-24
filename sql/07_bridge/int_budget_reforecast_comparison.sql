-- Phase 7. Central Board Budget vs. Independent Base Reforecast comparison, FY2026, metric x
-- segment grain. Every downstream bridge and the commentary engine reads this rather than
-- re-querying fact_budget / fct_pnl_reforecast / fct_arr_forecast independently, so one place
-- defines "what is Budget" and "what is Base" for every headline ARR, revenue, COGS, OpEx and
-- headcount line. fact_forecast (the source Q2 reforecast) is never read here -- the primary
-- story is Board Budget -> Independent Base, per docs/forecast_runway.md section 1.
--
-- ARR movement components (New Logo / Expansion / Reactivation / Contraction / Churn) carry NO
-- segment grain in fact_budget -- the memo accounts (9010-9050) post only to CC-9000,
-- company-level, every month (docs/data_dictionary.md; config/assumptions.yml
-- planning.budget carries only company totals). This is the identical constraint
-- docs/gtm_finance.md's "Segment allocation of the target" section already hit and solved for
-- New Logo ARR. Segment rows for those five components therefore carry an ALLOCATED Budget
-- figure (`budget_grain = 'allocated'`); Base's segment figures are always segment-native
-- (fct_arr_forecast is built bottom-up by segment) and are never allocated. Beginning ARR by
-- segment is real, shared history (the actual 31-Dec-2025 close, common to both Budget and
-- Base) rather than a Budget assumption, so it carries no allocation at all.
--
-- Allocation bases, reusing established Phase 5 methodology rather than inventing a new one:
--   New Logo ARR     int_gtm_new_logo_mix.share_of_company_new_logo_arr -- the FY2025 New Logo
--                     ARR mix by segment docs/gtm_finance.md already uses to allocate the New
--                     Logo ARR target by segment.
--   Expansion / Reactivation / Contraction / Churn
--                     each segment's share of actual 31-Dec-2025 ARR (fct_arr_waterfall) -- the
--                     most defensible available basis for movements that scale with the size of
--                     the installed base, in the absence of any segment-level Board plan for
--                     these lines.
-- Because the allocation shares sum to 1.0 by construction, segment rows always sum exactly
-- back to the Total row on both the Budget and the Base side -- ctl_bridge_commentary check B.
with fy26_months as (
    select month_end_date from dim_date
    where month_end_date between date '2026-01-31' and date '2026-12-31'
),

-- ============================================================================
-- ARR -- company-level Budget movements (real, from the memo accounts)
-- ============================================================================
budget_arr_company as (
    select
        case account_code
            when 9010 then 'new_logo_arr' when 9020 then 'expansion_arr'
            when 9030 then 'reactivation_arr' when 9040 then 'contraction_arr'
            when 9050 then 'churn_arr' end as metric,
        sum(budget_amount) as budget_amount
    from stg_fact_budget
    where account_code in (9010, 9020, 9030, 9040, 9050)
      and month_end_date in (select month_end_date from fy26_months)
    group by 1
),

base_arr_movement_monthly as (
    select segment, month_end_date, 'new_logo_arr' as metric, new_logo_arr as val from fct_arr_forecast where path = 'Base'
    union all select segment, month_end_date, 'expansion_arr', expansion_arr from fct_arr_forecast where path = 'Base'
    union all select segment, month_end_date, 'reactivation_arr', reactivation_arr from fct_arr_forecast where path = 'Base'
    union all select segment, month_end_date, 'contraction_arr', contraction_arr from fct_arr_forecast where path = 'Base'
    union all select segment, month_end_date, 'churn_arr', churn_arr from fct_arr_forecast where path = 'Base'
),

base_arr_company as (
    select metric, sum(val) as base_amount
    from base_arr_movement_monthly
    where segment = 'Total' and month_end_date in (select month_end_date from fy26_months)
    group by 1
),

arr_company_movement as (
    select 'Total' as segment, b.metric, b.budget_amount, ba.base_amount, 'source' as budget_grain
    from budget_arr_company b
    join base_arr_company ba using (metric)
),

-- ============================================================================
-- ARR -- segment allocation of the Budget's company-level movements
-- ============================================================================
new_logo_share as (
    select segment, share_of_company_new_logo_arr as share from int_gtm_new_logo_mix
),

arr_share_2025_12 as (
    select segment, ending_arr / sum(ending_arr) over () as share
    from fct_arr_waterfall
    where month_end_date = date '2025-12-31' and segment <> 'Total'
),

segment_new_logo_alloc as (
    select nl.segment, 'new_logo_arr' as metric, c.budget_amount * nl.share as budget_amount
    from new_logo_share nl
    cross join (select budget_amount from arr_company_movement where metric = 'new_logo_arr') c
),

segment_other_alloc as (
    select a.segment, m.metric, m.budget_amount * a.share as budget_amount
    from arr_share_2025_12 a
    cross join (
        select metric, budget_amount from arr_company_movement
        where metric in ('expansion_arr', 'reactivation_arr', 'contraction_arr', 'churn_arr')
    ) m
),

segment_alloc_all as (
    select * from segment_new_logo_alloc
    union all
    select * from segment_other_alloc
),

base_arr_segment as (
    select segment, metric, sum(val) as base_amount
    from base_arr_movement_monthly
    where segment <> 'Total' and month_end_date in (select month_end_date from fy26_months)
    group by 1, 2
),

arr_segment_movement as (
    select sa.segment, sa.metric, sa.budget_amount, bs.base_amount, 'allocated' as budget_grain
    from segment_alloc_all sa
    join base_arr_segment bs on bs.segment = sa.segment and bs.metric = sa.metric
),

all_arr_movement as (
    select * from arr_company_movement
    union all
    select * from arr_segment_movement
),

-- ============================================================================
-- ARR -- beginning (real, shared, both sides identical) and ending (derived)
-- ============================================================================
beginning_arr_rows as (
    select segment, 'beginning_arr' as metric, ending_arr as budget_amount, ending_arr as base_amount, 'source' as budget_grain
    from fct_arr_waterfall
    where month_end_date = date '2025-12-31'
),

ending_arr_calc as (
    select b.segment, b.budget_amount as beginning_budget, sum(mv.budget_amount) as movement_budget_sum
    from beginning_arr_rows b
    join all_arr_movement mv on mv.segment = b.segment
    group by 1, 2
),

ending_arr_base as (
    select segment, ending_arr as base_amount
    from fct_arr_forecast
    where path = 'Base' and month_end_date = date '2026-12-31'
),

ending_arr_rows as (
    select e.segment, 'ending_arr' as metric,
           e.beginning_budget + e.movement_budget_sum as budget_amount,
           b.base_amount,
           case when e.segment = 'Total' then 'source' else 'allocated' end as budget_grain
    from ending_arr_calc e
    join ending_arr_base b on b.segment = e.segment
),

arr_rows as (
    select 'arr' as metric_group, segment, metric, budget_amount, base_amount, budget_grain from beginning_arr_rows
    union all
    select 'arr', segment, metric, budget_amount, base_amount, budget_grain from all_arr_movement
    union all
    select 'arr', segment, metric, budget_amount, base_amount, budget_grain from ending_arr_rows
),

-- ============================================================================
-- Revenue, COGS, OpEx -- company-level, real on both sides (fact_budget carries full GL grain)
-- ============================================================================
revenue_budget as (
    select
        sum(case when account_code in (4000, 4010) then -budget_amount else 0 end) as subscription_revenue,
        sum(case when account_code in (4100, 4110) then -budget_amount else 0 end) as services_revenue
    from stg_fact_budget
    where month_end_date in (select month_end_date from fy26_months)
),

revenue_base as (
    select sum(subscription_revenue) as subscription_revenue, sum(services_revenue) as services_revenue
    from fct_pnl_reforecast
    where path = 'Base' and month_end_date in (select month_end_date from fy26_months)
),

revenue_rows as (
    select 'revenue' as metric_group, 'Total' as segment, 'subscription_revenue' as metric,
           rb.subscription_revenue as budget_amount, ba.subscription_revenue as base_amount, 'source' as budget_grain
    from revenue_budget rb cross join revenue_base ba
    union all
    select 'revenue', 'Total', 'services_revenue', rb.services_revenue, ba.services_revenue, 'source'
    from revenue_budget rb cross join revenue_base ba
    union all
    select 'revenue', 'Total', 'total_revenue',
           rb.subscription_revenue + rb.services_revenue, ba.subscription_revenue + ba.services_revenue, 'source'
    from revenue_budget rb cross join revenue_base ba
),

cogs_budget as (
    select
        sum(case when account_category = 'Subscription COGS' then budget_amount else 0 end) as subscription_cogs,
        sum(case when account_category = 'Services COGS' then budget_amount else 0 end) as services_cogs
    from stg_fact_budget
    where month_end_date in (select month_end_date from fy26_months)
),

cogs_base as (
    select sum(subscription_cogs) as subscription_cogs, sum(services_cogs) as services_cogs
    from fct_pnl_reforecast
    where path = 'Base' and month_end_date in (select month_end_date from fy26_months)
),

cogs_rows as (
    select 'cogs' as metric_group, 'Total' as segment, 'subscription_cogs' as metric,
           cb.subscription_cogs as budget_amount, cba.subscription_cogs as base_amount, 'source' as budget_grain
    from cogs_budget cb cross join cogs_base cba
    union all
    select 'cogs', 'Total', 'services_cogs', cb.services_cogs, cba.services_cogs, 'source'
    from cogs_budget cb cross join cogs_base cba
    union all
    select 'cogs', 'Total', 'total_cogs',
           cb.subscription_cogs + cb.services_cogs, cba.subscription_cogs + cba.services_cogs, 'source'
    from cogs_budget cb cross join cogs_base cba
),

opex_budget as (
    select
        sum(case when account_category = 'Sales & Marketing' then budget_amount else 0 end) as sales_marketing,
        sum(case when account_category = 'Research & Development' then budget_amount else 0 end) as research_development,
        sum(case when account_category = 'General & Administrative' then budget_amount else 0 end) as general_administrative
    from stg_fact_budget
    where month_end_date in (select month_end_date from fy26_months)
),

opex_base as (
    select sum(sales_marketing) as sales_marketing, sum(research_development) as research_development,
           sum(general_administrative) as general_administrative
    from fct_pnl_reforecast
    where path = 'Base' and month_end_date in (select month_end_date from fy26_months)
),

opex_rows as (
    select 'opex' as metric_group, 'Total' as segment, 'sales_marketing' as metric,
           ob.sales_marketing as budget_amount, oba.sales_marketing as base_amount, 'source' as budget_grain
    from opex_budget ob cross join opex_base oba
    union all
    select 'opex', 'Total', 'research_development', ob.research_development, oba.research_development, 'source'
    from opex_budget ob cross join opex_base oba
    union all
    select 'opex', 'Total', 'general_administrative', ob.general_administrative, oba.general_administrative, 'source'
    from opex_budget ob cross join opex_base oba
    union all
    select 'opex', 'Total', 'total_opex',
           ob.sales_marketing + ob.research_development + ob.general_administrative,
           oba.sales_marketing + oba.research_development + oba.general_administrative, 'source'
    from opex_budget ob cross join opex_base oba
),

-- ============================================================================
-- COGS / OpEx driver decomposition -- payroll / commission / non-payroll, by P&L category.
-- Budget side: real, straight from fact_budget's own account-code grain (6000/6010/6020
-- payroll, 6030 commission, everything else non-payroll). Base side: H1 2026 is real actual GL
-- (same account-code split, since Jan-Jun is replicated unchanged); H2 2026 is recomputed with
-- the EXACT SAME formulas fct_pnl_reforecast.sql uses internally (headcount x loaded cost per
-- FTE for payroll, the commission formula for Sales & Marketing, the flat trailing-quarter run
-- rate for non-payroll) -- reusing that logic rather than rebuilding a parallel cost forecast.
-- ============================================================================
categories as (
    select 'Subscription COGS' as account_category, 'subscription_cogs' as prefix
    union all select 'Services COGS', 'services_cogs'
    union all select 'Sales & Marketing', 'sales_marketing'
    union all select 'Research & Development', 'research_development'
    union all select 'General & Administrative', 'general_administrative'
),

budget_driver as (
    select account_category,
        sum(case when account_code in (6000, 6010, 6020) then budget_amount else 0 end) as payroll,
        sum(case when account_code = 6030 then budget_amount else 0 end) as commission,
        sum(case when account_code not in (6000, 6010, 6020, 6030) then budget_amount else 0 end) as nonpayroll
    from stg_fact_budget
    where month_end_date in (select month_end_date from fy26_months)
      and account_category in (select account_category from categories)
    group by 1
),

base_driver_h1 as (
    select account_category,
        sum(case when account_code in (6000, 6010, 6020) then actual_amount else 0 end) as payroll,
        sum(case when account_code = 6030 then actual_amount else 0 end) as commission,
        sum(case when account_code not in (6000, 6010, 6020, 6030) then actual_amount else 0 end) as nonpayroll
    from stg_fact_gl_actuals
    where month_end_date between date '2026-01-31' and date '2026-06-30'
      and account_category in (select account_category from categories)
    group by 1
),

function_category_share as (
    select 'Sales' as function, 'Sales & Marketing' as category, 1.00 as share
    union all select 'Marketing', 'Sales & Marketing', 1.00
    union all select 'Customer Success', 'Subscription COGS', 0.60
    union all select 'Customer Success', 'Sales & Marketing', 0.40
    union all select 'Support & Cloud Ops', 'Subscription COGS', 1.00
    union all select 'Professional Services', 'Services COGS', 1.00
    union all select 'Engineering', 'Research & Development', 1.00
    union all select 'Product & Design', 'Research & Development', 1.00
    union all select 'G&A', 'General & Administrative', 1.00
),

payroll_cost_per_fte as (
    select segment as function, value from int_forecast_drivers
    where driver_category = 'opex' and driver_name = 'payroll_cost_per_fte_monthly'
),

base_payroll_h2 as (
    select fcs.category as account_category, sum(hf.ending_headcount * pcf.value * fcs.share) as payroll
    from fct_headcount_forecast hf
    join function_category_share fcs on fcs.function = hf.function
    join payroll_cost_per_fte pcf on pcf.function = hf.function
    where hf.path = 'Base' and hf.is_actual = false
      and hf.month_end_date between date '2026-07-31' and date '2026-12-31'
    group by 1
),

non_payroll_flat_monthly as (
    select account_category, sum(actual_amount) / 3.0 as monthly_amount
    from stg_fact_gl_actuals
    where month_end_date between date '2026-04-30' and date '2026-06-30'
      and account_code not in (6000, 6010, 6020, 6030)
      and account_category in (select account_category from categories)
    group by 1
),

base_nonpayroll_h2 as (
    select account_category, monthly_amount * 6.0 as nonpayroll
    from non_payroll_flat_monthly
),

base_commission_h2 as (
    select sum(0.41 * (new_logo_arr * 0.09 + greatest(expansion_arr, 0) * 0.06)) as commission
    from fct_arr_forecast
    where path = 'Base' and segment = 'Total' and month_end_date between date '2026-07-31' and date '2026-12-31'
),

base_driver_full as (
    select
        c.account_category, c.prefix,
        coalesce(h1.payroll, 0) + coalesce(h2.payroll, 0) as payroll,
        coalesce(h1.commission, 0)
            + case when c.account_category = 'Sales & Marketing' then coalesce((select commission from base_commission_h2), 0) else 0 end
            as commission,
        coalesce(h1.nonpayroll, 0) + coalesce(np.nonpayroll, 0) as nonpayroll
    from categories c
    left join base_driver_h1 h1 on h1.account_category = c.account_category
    left join base_payroll_h2 h2 on h2.account_category = c.account_category
    left join base_nonpayroll_h2 np on np.account_category = c.account_category
),

driver_rows as (
    select
        case when c.account_category in ('Subscription COGS', 'Services COGS') then 'cogs_driver' else 'opex_driver' end as metric_group,
        'Total' as segment, c.prefix || '_payroll' as metric, bd.payroll as budget_amount, bf.payroll as base_amount, 'source' as budget_grain
    from categories c
    join budget_driver bd on bd.account_category = c.account_category
    join base_driver_full bf on bf.account_category = c.account_category
    union all
    select
        case when c.account_category in ('Subscription COGS', 'Services COGS') then 'cogs_driver' else 'opex_driver' end,
        'Total', c.prefix || '_nonpayroll', bd.nonpayroll, bf.nonpayroll, 'source'
    from categories c
    join budget_driver bd on bd.account_category = c.account_category
    join base_driver_full bf on bf.account_category = c.account_category
    union all
    select 'opex_driver', 'Total', 'sales_marketing_commission', bd.commission, bf.commission, 'source'
    from budget_driver bd
    join base_driver_full bf on bf.account_category = bd.account_category
    where bd.account_category = 'Sales & Marketing'
),

-- ============================================================================
-- Headcount -- company-level only (fact_budget account 9200 has no functional grain)
-- ============================================================================
headcount_rows as (
    select 'headcount' as metric_group, 'Total' as segment, 'ending_headcount' as metric,
           b.budget_amount, base.base_amount, 'source' as budget_grain
    from (select budget_amount from stg_fact_budget where account_code = 9200 and month_end_date = date '2026-12-31') b
    cross join (select sum(ending_headcount) as base_amount from fct_headcount_forecast
                where path = 'Base' and month_end_date = date '2026-12-31') base
)

select metric_group, segment, metric, budget_amount, base_amount, budget_grain
from (
    select * from arr_rows
    union all select * from revenue_rows
    union all select * from cogs_rows
    union all select * from opex_rows
    union all select * from driver_rows
    union all select * from headcount_rows
)
order by metric_group, segment, metric
