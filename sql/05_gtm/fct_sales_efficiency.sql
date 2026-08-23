-- Net ARR Sales Efficiency and the classic Magic Number, kept as two separate quarterly columns
-- with two different formulas and two different numerators (PHASE1_SPEC 8.4, binding) -- never
-- blended into one "efficiency" figure. Both use TOTAL Sales & Marketing expense in the prior
-- quarter, never the new-logo allocation from int_gtm_cost_allocation, which belongs to CAC only.
--
--   Net ARR Sales Efficiency = Net New ARR (quarter Q, fct_arr_waterfall)                 / Total S&M (Q-1)
--   Magic Number (classic)   = (Subscription Revenue Q - Subscription Revenue Q-1) x 4    / Total S&M (Q-1)
--
-- Grain: fiscal quarter, starting the second actual quarter -- the first (2024Q1) has no
-- prior-quarter S&M in fact_gl_actuals, which begins January 2024 (docs/data_dictionary.md).
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
    select cur.fiscal_quarter, cur.quarter_end, prev.fiscal_quarter as prior_fiscal_quarter
    from quarters_seq cur
    join quarters_seq prev on prev.qn = cur.qn - 1
),

net_new_arr_by_quarter as (
    select
        d.fiscal_quarter,
        sum(w.new_logo_arr + w.expansion_arr + w.reactivation_arr + w.contraction_arr + w.churn_arr) as net_new_arr
    from fct_arr_waterfall w
    join dim_date d on d.month_end_date = w.month_end_date
    where w.segment = 'Total' and d.is_actual
    group by 1
),

sm_by_quarter as (
    select d.fiscal_quarter, sum(g.actual_amount) as total_sm
    from stg_fact_gl_actuals g
    join dim_date d on d.month_end_date = g.month_end_date
    where g.account_category = 'Sales & Marketing'
    group by 1
),

subscription_revenue_by_quarter as (
    select d.fiscal_quarter, -sum(g.actual_amount) as subscription_revenue
    from stg_fact_gl_actuals g
    join dim_date d on d.month_end_date = g.month_end_date
    where g.account_category = 'Subscription Revenue'
    group by 1
)

select
    q.fiscal_quarter,
    q.quarter_end,
    nn.net_new_arr,
    sm_prior.total_sm as prior_quarter_sm,
    nn.net_new_arr / nullif(sm_prior.total_sm, 0) as net_arr_sales_efficiency,
    sr.subscription_revenue,
    sr_prior.subscription_revenue as subscription_revenue_prior_quarter,
    (sr.subscription_revenue - sr_prior.subscription_revenue) * 4 / nullif(sm_prior.total_sm, 0) as magic_number
from quarter_with_prior q
join net_new_arr_by_quarter nn on nn.fiscal_quarter = q.fiscal_quarter
join subscription_revenue_by_quarter sr on sr.fiscal_quarter = q.fiscal_quarter
join sm_by_quarter sm_prior on sm_prior.fiscal_quarter = q.prior_fiscal_quarter
join subscription_revenue_by_quarter sr_prior on sr_prior.fiscal_quarter = q.prior_fiscal_quarter
order by q.quarter_end
