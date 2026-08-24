-- Build gate for Phase 8 (deferred revenue / billing mechanics and ASC 340-40 sales commission
-- capitalisation). Any row this query returns is a violation and the build exits non-zero. An
-- empty result set is PASS. Same grain / grain_key / implied_value / bound convention as
-- ctl_forecast_controls.sql and ctl_bridge_commentary.sql.
--
--   A  deferred_revenue_rollforward   Beginning + Billings - Revenue = Ending, both the gross
--                                     form (with the arrears unbilled-receivable movement stated)
--                                     and the net-position form, every month x segment
--   B  no_negative_balances           no negative deferred revenue and no negative unbilled
--                                     receivable, at contract-month grain and rolled up. The
--                                     arrears unbilled receivable is modelled as its own positive
--                                     balance rather than allowed to appear as negative deferral
--   C  billing_completeness           every eligible contract-month with in-force subscription
--                                     revenue is in the schedule with revenue equal to source
--                                     MRR; every advance contract carries exactly the number of
--                                     invoices its cadence implies; no duplicate contract-months;
--                                     no invoice reaches more than 12 months forward, which is
--                                     what makes long-term deferred revenue structurally zero
--   D  revenue_reconciliation         contract accounting revenue within 8% of source GL every
--                                     month from Feb-2024, and within 4% for FY2025 as a whole.
--                                     Jan-2024 is excluded: it is a ledger boundary artifact of
--                                     the source's own lag convention, published not hidden
--   E  commission_earned              earned commission recomputed INDEPENDENTLY from
--                                     stg_fact_crm_opportunity x the approved rates, bypassing
--                                     every 05_gtm and 09_accounting model; and lost / open
--                                     opportunities earn nothing
--   F  capitalisation_identity        immediate expense + capitalised = earned commission
--   G  commission_asset_rollforward   Beginning + capitalised - amortisation = Ending
--   H  no_amortisation_before_capitalisation   no amortisation row precedes its own cohort month
--   I  useful_life_respected          no cohort amortises for more than 36 months and no cohort
--                                     amortises more than it capitalised
--   J  no_negative_commission_asset   ending commission asset never negative, any path or month
--   K  pnl_commission_reconciliation  immediate + amortisation = GAAP commission expense, every
--                                     row; and in ACTUAL months both components tie to the source
--                                     ledger, account 6030 and account 6040, within $1
--   L  frozen_outputs_unchanged       every Phase 6 line this phase reads back out is identical
--                                     to the frozen fct_pnl_reforecast and fct_arr_forecast
--                                     values, so the accounting layer demonstrably changed no
--                                     commercial output
--   M  no_duplicate_records           no duplicate keys in any Phase 8 fct_ model
-- Every rollforward below is RECOMPUTED from the stored component columns rather than read out
-- of the model's own residual column, and every opening balance is re-derived as the prior
-- month's stored closing balance rather than taken from the model's own beginning-balance
-- column. A control that reads a model's own residual only proves the model can subtract; a
-- control that re-derives the identity proves the balances themselves tie.
with deferred_revenue_rollforward as (
    select 'deferred_revenue_rollforward' as grain,
           segment || ' / ' || month_end_date::varchar as grain_key,
           ending_deferred_revenue as implied_value,
           beginning_deferred_revenue + billings - revenue_recognised
             + unbilled_receivable_movement as bound
    from fct_deferred_revenue
    where abs(ending_deferred_revenue
              - (beginning_deferred_revenue + billings - revenue_recognised
                 + unbilled_receivable_movement)) >= 1.00
    union all
    select 'deferred_revenue_rollforward_net',
           segment || ' / ' || month_end_date::varchar,
           ending_deferred_revenue - ending_unbilled_receivable,
           beginning_deferred_revenue - beginning_unbilled_receivable + billings - revenue_recognised
    from fct_deferred_revenue
    where abs((ending_deferred_revenue - ending_unbilled_receivable)
              - (beginning_deferred_revenue - beginning_unbilled_receivable
                 + billings - revenue_recognised)) >= 1.00
    union all
    -- Opening balance re-derived from the prior month's stored closing balance, so a model that
    -- computed its own opening column wrongly cannot pass by being internally consistent.
    select 'deferred_revenue_opening_ties_to_prior_close',
           segment || ' / ' || month_end_date::varchar,
           beginning_deferred_revenue, prior_close
    from (
        select segment, month_end_date, beginning_deferred_revenue,
               lag(ending_deferred_revenue) over (partition by segment order by month_end_date)
                   as prior_close
        from fct_deferred_revenue
    ) t
    where prior_close is not null and abs(beginning_deferred_revenue - prior_close) >= 1.00
    union all
    -- The reported balance re-aggregated straight from the contract schedule, bypassing
    -- fct_deferred_revenue's own grouping entirely.
    select 'deferred_revenue_ties_to_contract_schedule',
           f.segment || ' / ' || f.month_end_date::varchar,
           f.ending_deferred_revenue, s.schedule_deferred_revenue
    from fct_deferred_revenue f
    join (
        select 'Total' as segment, month_end_date,
               sum(greatest(net_contract_position, 0.0)) as schedule_deferred_revenue
        from int_contract_billing_schedule
        where month_end_date between date '2024-01-31' and date '2026-06-30'
        group by 2
    ) s on s.segment = f.segment and s.month_end_date = f.month_end_date
    where abs(f.ending_deferred_revenue - s.schedule_deferred_revenue) >= 1.00
    union all
    -- The schedule must also self-liquidate: every contract's final net position is zero, which
    -- is what proves no deferred revenue was created that no revenue ever unwinds.
    select 'contract_position_self_liquidates', contract_id, final_position, 0.0
    from (
        select contract_id,
               last(net_contract_position order by month_end_date) as final_position
        from int_contract_billing_schedule
        group by 1
    ) t
    where abs(final_position) >= 0.01
),

no_negative_balances as (
    select 'no_negative_deferred_revenue' as grain,
           contract_id || ' / ' || month_end_date::varchar as grain_key,
           deferred_revenue as implied_value, 0.0 as bound
    from int_contract_billing_schedule
    where deferred_revenue < -0.005
    union all
    select 'no_negative_unbilled_receivable',
           contract_id || ' / ' || month_end_date::varchar,
           unbilled_receivable, 0.0
    from int_contract_billing_schedule
    where unbilled_receivable < -0.005
    union all
    select 'no_negative_deferred_revenue_reported',
           segment || ' / ' || month_end_date::varchar,
           ending_deferred_revenue, 0.0
    from fct_deferred_revenue
    where ending_deferred_revenue < -0.005 or ending_unbilled_receivable < -0.005
),

billing_completeness as (
    -- Every month a contract carries subscription MRR in the source, the schedule recognises
    -- exactly that MRR. Nothing eligible is missing and nothing extra has been created.
    select 'billing_completeness_revenue' as grain,
           s.contract_id || ' / ' || s.month_end_date::varchar as grain_key,
           coalesce(b.subscription_revenue_recognised, -1) as implied_value,
           s.mrr::double as bound
    from (
        select contract_id, month_end_date, sum(mrr)::double as mrr
        from stg_fact_subscription_monthly
        where month_end_date between date '2024-01-31' and date '2026-06-30'
        group by 1, 2
    ) s
    left join int_contract_billing_schedule b
           on b.contract_id = s.contract_id and b.month_end_date = s.month_end_date
    where abs(coalesce(b.subscription_revenue_recognised, -1) - s.mrr) >= 0.01
    union all
    -- Every advance-billed contract raises exactly ceil(committed life / cadence) invoices.
    select 'billing_completeness_anchor_count', t.contract_id,
           t.anchor_count::double, t.expected_anchors::double
    from (
        select contract_id,
               count(*) filter (where is_billing_anchor) as anchor_count,
               ceil(max(period_offset + 1)::double / max(billing_period_months)) as expected_anchors
        from int_contract_billing_schedule
        where bills_in_advance
        group by 1
    ) t
    where t.anchor_count <> t.expected_anchors
    union all
    select 'no_duplicate_contract_month', contract_id || ' / ' || month_end_date::varchar,
           count(*)::double, 1.0
    from int_contract_billing_schedule
    group by 1, 2
    having count(*) > 1
    union all
    -- No invoice reaches beyond 12 months, which is why long-term deferred revenue is zero.
    select 'no_billing_period_beyond_12_months', segment || ' / ' || month_end_date::varchar,
           max_months_to_period_end::double, 12.0
    from fct_deferred_revenue
    where max_months_to_period_end > 12
),

revenue_reconciliation as (
    select 'revenue_reconciliation_monthly' as grain,
           month_end_date::varchar as grain_key,
           residual_vs_gl_pct as implied_value, 0.08 as bound
    from fct_revenue_accounting_reconciliation
    where not is_ledger_boundary_month
      and abs(residual_vs_gl_pct) >= 0.08
    union all
    select 'revenue_reconciliation_fy2025', 'FY2025',
           sum(contract_accounting_revenue) / nullif(sum(gl_subscription_revenue), 0) - 1, 0.04
    from fct_revenue_accounting_reconciliation
    where fiscal_year = 2025
    having abs(sum(contract_accounting_revenue) / nullif(sum(gl_subscription_revenue), 0) - 1) >= 0.04
),

commission_earned as (
    -- INDEPENDENT recomputation. Reads stg_fact_crm_opportunity directly, applies the approved
    -- rates by deal type, and compares to what the accounting layer produced. Deliberately
    -- bypasses int_crm_opportunity_normalized, int_crm_closed_won and int_commission_earned so a
    -- shared error in that chain cannot pass this control.
    select 'commission_earned_recomputed' as grain,
           i.month_end_date::varchar as grain_key,
           i.earned as implied_value, x.expected as bound
    from (
        select month_end_date, sum(commission_earned) as earned
        from int_commission_earned
        where path = 'Base' and is_actual
        group by 1
    ) i
    join (
        select last_day(actual_close_date) as month_end_date,
               sum(acv * case deal_type when 'New Logo' then 0.09
                                        when 'Expansion' then 0.06
                                        when 'Renewal Uplift' then 0.03 else 0 end) as expected
        from stg_fact_crm_opportunity
        where status = 'Won'
          and actual_close_date is not null
          and last_day(actual_close_date) between date '2024-01-31' and date '2026-06-30'
        group by 1
    ) x on x.month_end_date = i.month_end_date
    where abs(i.earned - x.expected) >= 0.01
    union all
    -- Lost and open opportunities must contribute nothing.
    select 'no_commission_on_lost_or_open', o.status,
           sum(o.acv)::double, 0.0
    from stg_fact_crm_opportunity o
    where o.status in ('Lost', 'Open')
      and exists (select 1 from int_crm_closed_won w where w.opportunity_id = o.opportunity_id)
    group by o.status
),

capitalisation_identity as (
    -- Immediate expense + capitalised = earned, recomputed from the two component columns
    -- rather than read from the model's own earned_recomposed column.
    select 'capitalisation_identity' as grain,
           path || ' / ' || month_end_date::varchar as grain_key,
           immediate_expense + capitalised_commission as implied_value,
           commission_earned as bound
    from fct_commission_asset
    where abs(immediate_expense + capitalised_commission - commission_earned) >= 0.01
),

commission_asset_rollforward as (
    -- Opening balance re-derived as the prior month's stored closing balance. fct_commission_asset
    -- publishes its beginning column as ending less the month's movements, so testing the
    -- identity against that column would be tautological; this tests the balances themselves.
    select 'commission_asset_rollforward' as grain,
           path || ' / ' || month_end_date::varchar as grain_key,
           ending_commission_asset as implied_value,
           coalesce(prior_asset, 0) + capitalised_commission - commission_amortisation as bound
    from (
        select path, month_end_date, ending_commission_asset, capitalised_commission,
               commission_amortisation,
               lag(ending_commission_asset) over (partition by path order by month_end_date)
                   as prior_asset
        from fct_commission_asset
    ) t
    where abs(ending_commission_asset
              - (coalesce(prior_asset, 0) + capitalised_commission - commission_amortisation)) >= 0.01
    union all
    select 'accrued_commission_liability_rollforward',
           path || ' / ' || month_end_date::varchar,
           ending_accrued_commission_liability,
           coalesce(prior_liability, 0) + commission_earned - commission_paid_cash
    from (
        select path, month_end_date, ending_accrued_commission_liability, commission_earned,
               commission_paid_cash,
               lag(ending_accrued_commission_liability) over (partition by path order by month_end_date)
                   as prior_liability
        from fct_commission_asset
    ) t
    where abs(ending_accrued_commission_liability
              - (coalesce(prior_liability, 0) + commission_earned - commission_paid_cash)) >= 0.01
    union all
    -- The asset re-derived independently as the sum of every cohort's unamortised balance,
    -- bypassing the cumulative-sum rollforward entirely.
    select 'commission_asset_ties_to_cohort_schedule',
           a.path || ' / ' || a.month_end_date::varchar,
           a.ending_commission_asset, c.cohort_unamortised
    from fct_commission_asset a
    join (
        select path, month_end_date, sum(unamortised_balance) as cohort_unamortised
        from fct_commission_amortization
        group by 1, 2
    ) c on c.path = a.path and c.month_end_date = a.month_end_date
    where abs(a.ending_commission_asset - c.cohort_unamortised) >= 0.01
),

no_amortisation_before_capitalisation as (
    select 'no_amortisation_before_capitalisation' as grain,
           path || ' / ' || cohort_month::varchar || ' / ' || month_end_date::varchar as grain_key,
           months_elapsed::double as implied_value, 0.0 as bound
    from fct_commission_amortization
    where month_end_date < cohort_month or months_elapsed < 0
),

useful_life_respected as (
    select 'useful_life_months_exceeded' as grain,
           path || ' / ' || cohort_month::varchar as grain_key,
           max(months_elapsed)::double as implied_value, 35.0 as bound
    from fct_commission_amortization
    group by 1, 2
    having max(months_elapsed) > 35
    union all
    -- A cohort can never amortise more than it capitalised. Cohorts whose 36-month schedule runs
    -- past the modelled calendar are excluded from this equality: they are correctly truncated,
    -- not over-amortised, so only the "more than capitalised" direction is tested.
    select 'cohort_amortisation_exceeds_capitalised',
           path || ' / ' || cohort_month::varchar,
           sum(monthly_amortisation), max(capitalised_amount)
    from fct_commission_amortization
    group by 1, 2
    having sum(monthly_amortisation) - max(capitalised_amount) >= 0.01
),

no_negative_commission_asset as (
    select 'no_negative_commission_asset' as grain,
           path || ' / ' || month_end_date::varchar as grain_key,
           ending_commission_asset as implied_value, 0.0 as bound
    from fct_commission_asset
    where ending_commission_asset < -0.01
),

pnl_commission_reconciliation as (
    select 'gaap_commission_expense_identity' as grain,
           path || ' / ' || month_end_date::varchar as grain_key,
           gaap_commission_expense as implied_value,
           immediate_expense + commission_amortisation as bound
    from fct_commission_asset
    where abs(gaap_commission_expense - (immediate_expense + commission_amortisation)) >= 0.01
    union all
    select 'immediate_expense_ties_to_account_6030',
           path || ' / ' || month_end_date::varchar,
           asc340_immediate_expense, gl_commission_expense_6030
    from fct_commission_accounting_reconciliation
    where is_actual and abs(residual_immediate_vs_gl) >= 1.00
    union all
    select 'amortisation_ties_to_account_6040',
           path || ' / ' || month_end_date::varchar,
           asc340_amortisation, gl_commission_amortisation_6040
    from fct_commission_accounting_reconciliation
    where is_actual and abs(residual_amortisation_vs_gl) >= 1.00
    union all
    -- In actual months the enhancement must be exactly nothing: Phase 8 reproduces the historical
    -- ledger rather than restating it.
    select 'no_adjustment_in_actual_months',
           path || ' / ' || month_end_date::varchar,
           commission_accounting_adjustment, 0.0
    from fct_commission_accounting_reconciliation
    where is_actual and abs(commission_accounting_adjustment) >= 1.00
),

frozen_outputs_unchanged as (
    select 'phase6_pnl_unchanged' as grain,
           e.path || ' / ' || e.month_end_date::varchar as grain_key,
           e.phase6_operating_income as implied_value, p.operating_income::double as bound
    from fct_accounting_enhanced_pnl e
    join fct_pnl_reforecast p on p.path = e.path and p.month_end_date = e.month_end_date
    where abs(e.phase6_operating_income - p.operating_income) >= 0.01
       or abs(e.phase6_sales_marketing - p.sales_marketing) >= 0.01
       or abs(e.phase6_total_revenue   - p.total_revenue)   >= 0.01
    union all
    -- The forecast commission base must be the frozen ARR movement, unmodified.
    select 'phase6_arr_forecast_unchanged',
           c.path || ' / ' || c.month_end_date::varchar,
           c.eligible_basis, f.new_logo_arr::double
    from int_commission_earned c
    join fct_arr_forecast f
      on f.path = c.path and f.month_end_date = c.month_end_date and f.segment = 'Total'
    where not c.is_actual and c.deal_type = 'New Logo'
      and abs(c.eligible_basis - f.new_logo_arr::double) >= 0.01
),

no_duplicate_records as (
    select 'no_duplicate_billings' as grain,
           segment || ' / ' || month_end_date::varchar as grain_key,
           count(*)::double as implied_value, 1.0 as bound
    from fct_billings group by 1, 2 having count(*) > 1
    union all
    select 'no_duplicate_deferred_revenue', segment || ' / ' || month_end_date::varchar,
           count(*)::double, 1.0
    from fct_deferred_revenue group by 1, 2 having count(*) > 1
    union all
    select 'no_duplicate_commission_asset', path || ' / ' || month_end_date::varchar,
           count(*)::double, 1.0
    from fct_commission_asset group by 1, 2 having count(*) > 1
    union all
    select 'no_duplicate_enhanced_pnl', path || ' / ' || month_end_date::varchar,
           count(*)::double, 1.0
    from fct_accounting_enhanced_pnl group by 1, 2 having count(*) > 1
    union all
    select 'no_duplicate_sensitivity',
           variant || ' / ' || path || ' / ' || month_end_date::varchar,
           count(*)::double, 1.0
    from fct_commission_sensitivity group by 1, 2 having count(*) > 1
)

select * from deferred_revenue_rollforward
union all select * from no_negative_balances
union all select * from billing_completeness
union all select * from revenue_reconciliation
union all select * from commission_earned
union all select * from capitalisation_identity
union all select * from commission_asset_rollforward
union all select * from no_amortisation_before_capitalisation
union all select * from useful_life_respected
union all select * from no_negative_commission_asset
union all select * from pnl_commission_reconciliation
union all select * from frozen_outputs_unchanged
union all select * from no_duplicate_records
order by grain, grain_key
