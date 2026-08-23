-- Build gate for Phase 4 (retention, cohorts, renewal base and outcomes). Any row this query
-- returns is a violation and the build exits non-zero. An empty result set is PASS.
--
--   A  grr_bounds                GRR <= 100%
--   B  grr_le_nrr                GRR <= NRR, every period and segment
--   C  logo_retention_bounds     0 <= logo retention <= 100%
--   D  cohort_denominator        TTM cohort beginning ARR > 0, every customer-month row
--   E  no_duplicate_cohort_rows  one customer-month row per (customer_id, month_end_date)
--   F  atr_non_negative          ATR is never negative
--   G  renewal_date_integrity    a renewal_base row's renewal_month actually contains the
--                                 contract's own renewal_date
--   H  renewal_outcome_tie       pre_renewal_arr + price_uplift_arr + seat_module_arr =
--                                 renewed_arr for a Renewed outcome; renewed_arr = 0 for a
--                                 Churned or Early Termination outcome
--   I  retention_source_tie      fct_retention_ttm.cohort_beginning_arr, independently
--                                 recomputed straight from int_arr_customer_month and
--                                 dim_customer, bypassing int_retention_cohort_customer_month
--                                 entirely
with grr_bounds as (
    select 'grr_bounds' as grain, segment || ' / ' || month_end_date::varchar as grain_key,
           grr as implied_value, 1.0 as bound
    from fct_retention_ttm
    where grr > 1.0 + 1e-9
),

grr_le_nrr as (
    select 'grr_le_nrr' as grain, segment || ' / ' || month_end_date::varchar as grain_key,
           grr as implied_value, nrr as bound
    from fct_retention_ttm
    where grr > nrr + 1e-9
),

logo_retention_bounds as (
    select 'logo_retention_bounds' as grain, segment || ' / ' || month_end_date::varchar as grain_key,
           logo_retention as implied_value, null::double as bound
    from fct_retention_ttm
    where logo_retention < 0 - 1e-9 or logo_retention > 1.0 + 1e-9
),

cohort_denominator as (
    select 'cohort_denominator' as grain, customer_id || ' / ' || month_end_date::varchar as grain_key,
           beginning_arr as implied_value, 0.0 as bound
    from int_retention_cohort_customer_month
    where beginning_arr <= 0
),

no_duplicate_cohort_rows as (
    select 'no_duplicate_cohort_rows' as grain, customer_id || ' / ' || month_end_date::varchar as grain_key,
           count(*)::double as implied_value, 1.0 as bound
    from int_retention_cohort_customer_month
    group by 1, 2
    having count(*) > 1
),

atr_non_negative as (
    select 'atr_non_negative' as grain, contract_id as grain_key,
           atr_arr as implied_value, 0.0 as bound
    from fct_renewal_base
    where atr_arr < 0
),

renewal_date_integrity as (
    select 'renewal_date_integrity' as grain, contract_id as grain_key,
           date_diff('day', date '1970-01-01', date_trunc('month', renewal_date))::double as implied_value,
           date_diff('day', date '1970-01-01', date_trunc('month', renewal_month))::double as bound
    from fct_renewal_base
    where date_trunc('month', renewal_date) <> date_trunc('month', renewal_month)
),

renewal_outcome_tie as (
    select 'renewal_outcome_tie' as grain, contract_id as grain_key,
           atr_arr + price_uplift_arr + seat_module_arr as implied_value,
           renewed_arr as bound
    from fct_renewal_outcomes
    where (
            renewal_outcome not in ('Churned', 'Early Termination')
            and abs((atr_arr + price_uplift_arr + seat_module_arr) - renewed_arr) >= 1.00
          )
       or (renewal_outcome in ('Churned', 'Early Termination') and renewed_arr <> 0)
),

retention_source_tie as (
    with reporting_months as (
        select distinct month_end_date as reporting_month
        from dim_date
        where is_actual
    ),
    independent as (
        select
            rm.reporting_month,
            cu.segment,
            sum(m12.end_arr) as recomputed_beginning_arr
        from reporting_months rm
        join dim_date d12
            on d12.month_end_date = (
                select m12d.month_end_date
                from dim_date m12d
                where m12d.month_end_date < rm.reporting_month
                order by m12d.month_end_date desc
                limit 1 offset 11
            )
        join int_arr_customer_month m12 on m12.month_end_date = d12.month_end_date and m12.end_arr > 0
        join dim_customer cu on cu.customer_id = m12.customer_id
        group by 1, 2
    )
    select
        'retention_source_tie' as grain,
        t.segment || ' / ' || t.month_end_date::varchar as grain_key,
        t.cohort_beginning_arr as implied_value,
        i.recomputed_beginning_arr as bound
    from fct_retention_ttm t
    join independent i on i.reporting_month = t.month_end_date and i.segment = t.segment
    where t.segment <> 'Total'
      and abs(t.cohort_beginning_arr - i.recomputed_beginning_arr) >= 1.00
),

all_checks as (
    select grain, grain_key, implied_value, bound from grr_bounds
    union all
    select grain, grain_key, implied_value, bound from grr_le_nrr
    union all
    select grain, grain_key, implied_value, bound from logo_retention_bounds
    union all
    select grain, grain_key, implied_value, bound from cohort_denominator
    union all
    select grain, grain_key, implied_value, bound from no_duplicate_cohort_rows
    union all
    select grain, grain_key, implied_value, bound from atr_non_negative
    union all
    select grain, grain_key, implied_value, bound from renewal_date_integrity
    union all
    select grain, grain_key, implied_value, bound from renewal_outcome_tie
    union all
    select grain, grain_key, implied_value, bound from retention_source_tie
)

select grain, grain_key, implied_value, bound
from all_checks
order by grain, grain_key
