-- CRM-to-ARR reconciliation bridge (PHASE1_SPEC 8.8), one row per named bridge line, for two
-- periods: FY2025 (the reconciling year, and the period the hard 0.5% tolerance control is
-- graded on) and TTM_2026_06 (trailing twelve months to the reporting date, informational --
-- see the right-censoring note in docs/gtm_finance.md on why the most recent months understate
-- provisioning). Three bridge_type values: 'New Logo', 'Expansion', and 'Combined' (the sum of
-- both residuals, used by ctl_gtm_controls against PHASE1_SPEC 8.8's literal "new-logo plus
-- expansion ARR" wording).
--
-- New Logo walk -- CUSTOMER-MATCHED, the rigorous case. Every New-Logo closed-won CRM
-- opportunity (int_crm_closed_won) is matched to that same customer's NEXT landing event in
-- fct_arr_movement on or after the CRM close month, among movement types 'New Logo' and
-- 'Reactivation'. Both types are eligible matches, not just 'New Logo': a churn-and-return
-- customer who signs a fresh CRM "New Logo" opportunity on their way back in lands in the ARR
-- engine as a Reactivation, not a second New Logo (a customer has exactly one New Logo row
-- ever, per docs/arr_engine.md's six classification rules) -- treating that as "non-provisioned"
-- would misclassify a real, landed booking. A non-provisioned win has no real customer_id
-- (int_crm_closed_won sets customer_id to null for it) and so correctly finds no match at all.
-- A separate small population runs the other direction: a handful of ARR-side New Logo events
-- have no CRM New-Logo opportunity at all, for any period -- self-serve new logos that never
-- went through a rep. That population is computed independently from the ARR side
-- (self_serve_new_logo below), not solved as a plug, the same way the Expansion bridge's
-- self-serve line is computed.
--
-- Expansion walk -- customer + time-window matched, deliberately NOT a forced 1:1
-- opportunity-to-ARR-event match. A customer can have many expansion events in one period, so
-- there is no unique "the" opportunity behind a given ARR movement the way there is for New
-- Logo (which happens exactly once per customer). Instead, every CRM Expansion/Renewal-Uplift
-- customer-month is classified against that customer's ARR history within a bounded window, and
-- every ARR Expansion customer-month is classified against that customer's CRM history within
-- the same window. The window is 0-2 months forward from the CRM close date, not an arbitrary
-- tuning choice: docs/generation_methodology.md section 7 documents "signature in one month and
-- activation in the next, or the one after" as the built-in provisioning-lag mechanism
-- (config/assumptions.yml crm.messiness.provisioning_lag_next_month_share /
-- _two_month_share), i.e. a 0-2 month lag by construction.
--
-- Five named items, none a balancing plug:
--   1. Absorbed into a non-Expansion net movement -- a CRM Expansion or Renewal Uplift closes,
--      but the customer's SAME-MONTH net ARR movement (customer-grain, one movement type per
--      PHASE1_SPEC 8.2) classifies as something else (No Change, Contraction, ...) because a
--      simultaneous seat/module cut offsets the gain, AND no later Expansion movement appears in
--      the window either. This is the same mechanism docs/retention_renewals.md already
--      documents for renewal outcomes: "Renewed with Contraction outcomes still carry a small
--      positive price_uplift_arr alongside a much larger negative seat_module_arr" -- a real
--      price rise that nets away at customer grain, not a data defect.
--   2. Recorded in the customer's own New-Logo month -- an Expansion-deal-type CRM opportunity
--      closes in the exact month a customer's ARR shows New Logo (a same-month product attach at
--      signing). That ACV is already inside the New Logo ARR bridge's landed figure, not
--      Expansion's -- PHASE1_SPEC 2.3 itself notes "~$0.2M of expansion is on within-year new
--      logos," so this is an expected, documented cross-bridge classification difference.
--   3. Activation timing: signed this period, lands later (or not within the window at all,
--      distinct from 1/2 above -- i.e. a genuine Expansion match exists but falls after period
--      end).
--   4. Activation timing: signed earlier period, lands this period.
--   5. Self-serve / sub-threshold expansion -- ARR Expansion landing this period for a customer
--      with NO CRM Expansion/Renewal-Uplift record anywhere in the window at all. Computed
--      independently from the ARR side, not solved as a plug: docs/generation_methodology.md
--      section 7 documents that expansions below crm.expansion_self_serve_threshold ($3,500)
--      mostly skip the CRM entirely (expansion_opportunity_share = 0.16 below threshold), so
--      this line is expected to be material.
--
-- What remains after these five is genuine noise -- primarily post-close amendments
-- (config/assumptions.yml crm.messiness.post_close_amendment_share, up to +/-22% of ACV) that
-- this reconciliation does not attempt to separately size, because the source data does not
-- carry a "revised ACV" field distinct from the frozen CRM record. See docs/gtm_finance.md.
with periods as (
    select 'FY2025' as period, date '2025-01-31' as period_start, date '2025-12-31' as period_end
    union all
    select 'TTM_2026_06', date '2025-07-31', date '2026-06-30'
),

landed_arr_by_period as (
    select p.period, sum(w.new_logo_arr) as new_logo_arr, sum(w.expansion_arr) as expansion_arr
    from periods p
    join fct_arr_waterfall w
        on w.segment = 'Total' and w.month_end_date between p.period_start and p.period_end
    group by 1
),

-- ---------------------------------------------------------------------------
-- New Logo bridge
-- ---------------------------------------------------------------------------
matched_new_logo as (
    select
        c.opportunity_id,
        c.customer_id,
        c.actual_close_month as crm_month,
        c.acv as crm_acv,
        (
            select m.month_end_date
            from fct_arr_movement m
            where m.customer_id = c.customer_id
              and m.movement_type in ('New Logo', 'Reactivation')
              and m.month_end_date >= c.actual_close_month
            order by m.month_end_date
            limit 1
        ) as arr_month
    from int_crm_closed_won c
    where c.deal_type = 'New Logo'
),

matched_new_logo_full as (
    select
        n.opportunity_id, n.customer_id, n.crm_month, n.crm_acv, n.arr_month,
        m.movement_arr as arr_new_logo_arr
    from matched_new_logo n
    left join fct_arr_movement m
        on m.customer_id = n.customer_id and m.month_end_date = n.arr_month
),

new_logo_components as (
    select
        p.period,
        sum(case when n.crm_month between p.period_start and p.period_end
                 then n.crm_acv else 0 end) as crm_new_logo_acv,
        sum(case when n.crm_month between p.period_start and p.period_end and n.arr_month is null
                 then n.crm_acv else 0 end) as non_provisioned_acv,
        sum(case when n.crm_month between p.period_start and p.period_end
                      and n.arr_month is not null and n.arr_month > p.period_end
                 then n.crm_acv else 0 end) as timing_out_acv,
        sum(case when n.arr_month between p.period_start and p.period_end and n.crm_month < p.period_start
                 then n.arr_new_logo_arr else 0 end) as timing_in_arr,
        sum(case when n.crm_month between p.period_start and p.period_end
                      and n.arr_month between p.period_start and p.period_end
                 then n.arr_new_logo_arr - n.crm_acv else 0 end) as amendment_arr
    from periods p
    cross join matched_new_logo_full n
    group by 1
),

-- A small population of ARR-side New Logo events has NO matching CRM New-Logo opportunity at
-- all, in any period -- self-serve new logos that never went through a rep, analogous to the
-- self-serve expansion population below. Computed the same way: independently, from the ARR
-- side, not solved as a plug.
self_serve_new_logo as (
    select p.period, sum(m.movement_arr) as self_serve_new_logo_arr
    from periods p
    join fct_arr_movement m
        on m.movement_type = 'New Logo' and m.month_end_date between p.period_start and p.period_end
    left join int_crm_closed_won c
        on c.deal_type = 'New Logo' and c.customer_id = m.customer_id
    where c.customer_id is null
    group by 1
),

new_logo_bridge as (
    select
        c.period, c.crm_new_logo_acv, c.non_provisioned_acv, c.timing_out_acv,
        c.timing_in_arr, c.amendment_arr,
        coalesce(s.self_serve_new_logo_arr, 0) as self_serve_new_logo_arr,
        l.new_logo_arr as landed_new_logo_arr,
        (c.crm_new_logo_acv - c.non_provisioned_acv - c.timing_out_acv + c.timing_in_arr + c.amendment_arr
            + coalesce(s.self_serve_new_logo_arr, 0)) as implied_landed_arr,
        l.new_logo_arr
            - (c.crm_new_logo_acv - c.non_provisioned_acv - c.timing_out_acv + c.timing_in_arr + c.amendment_arr
               + coalesce(s.self_serve_new_logo_arr, 0))
            as unexplained_residual
    from new_logo_components c
    join landed_arr_by_period l on l.period = c.period
    left join self_serve_new_logo s on s.period = c.period
),

new_logo_rows as (
    select period, 'New Logo' as bridge_type, 1 as line_order, 'Closed-Won CRM New Logo ACV' as line_item, crm_new_logo_acv as amount from new_logo_bridge
    union all
    select period, 'New Logo', 2, 'Non-provisioned wins (never activated)', -non_provisioned_acv from new_logo_bridge
    union all
    select period, 'New Logo', 3, 'Activation timing: signed this period, lands later', -timing_out_acv from new_logo_bridge
    union all
    select period, 'New Logo', 4, 'Activation timing: signed earlier, lands this period', timing_in_arr from new_logo_bridge
    union all
    select period, 'New Logo', 5, 'Post-close amendments (ACV vs. landed ARR, same-period signings)', amendment_arr from new_logo_bridge
    union all
    select period, 'New Logo', 6, 'New Logo ARR without a matching CRM opportunity (self-serve)', self_serve_new_logo_arr from new_logo_bridge
    union all
    select period, 'New Logo', 7, 'Landed New Logo ARR (fct_arr_waterfall)', landed_new_logo_arr from new_logo_bridge
    union all
    select period, 'New Logo', 8, 'Unexplained residual', unexplained_residual from new_logo_bridge
),

-- ---------------------------------------------------------------------------
-- Expansion bridge
-- ---------------------------------------------------------------------------
crm_expansion_uplift as (
    select customer_id, actual_close_month as crm_month, deal_type, sum(acv) as crm_acv
    from int_crm_closed_won
    where deal_type in ('Expansion', 'Renewal Uplift') and customer_id is not null
    group by 1, 2, 3
),

-- Every CRM Expansion/Renewal-Uplift customer-month, classified against that customer's own ARR
-- history: does an Expansion movement appear for them within [crm_month, crm_month + 2 months]?
-- If not, what actually happened in the SAME month explains why (New Logo, or netted away).
crm_classified as (
    select
        c.customer_id, c.crm_month, c.deal_type, c.crm_acv,
        m_same.movement_type as same_month_movement_type,
        (
            select mm.month_end_date
            from fct_arr_movement mm
            where mm.customer_id = c.customer_id
              and mm.movement_type = 'Expansion'
              and mm.month_end_date between c.crm_month and c.crm_month + interval 2 month
            order by mm.month_end_date
            limit 1
        ) as matched_expansion_month
    from crm_expansion_uplift c
    left join fct_arr_movement m_same
        on m_same.customer_id = c.customer_id and m_same.month_end_date = c.crm_month
),

crm_final as (
    select
        *,
        case
            when matched_expansion_month is not null then 'matched'
            when same_month_movement_type = 'New Logo' then 'new_logo_month'
            else 'absorbed'
        end as classification
    from crm_classified
),

-- Every ARR Expansion customer-month, classified against that customer's own CRM history: does a
-- CRM Expansion/Renewal-Uplift closing exist within [arr_month - 2 months, arr_month]? The
-- nearest (most recent) one is used, mirroring the forward search on the CRM side above.
arr_expansion as (
    select customer_id, month_end_date as arr_month, movement_arr
    from fct_arr_movement
    where movement_type = 'Expansion'
),

arr_final as (
    select
        a.customer_id, a.arr_month, a.movement_arr,
        (
            select c.crm_month
            from crm_expansion_uplift c
            where c.customer_id = a.customer_id
              and c.crm_month between a.arr_month - interval 2 month and a.arr_month
            order by c.crm_month desc
            limit 1
        ) as matched_crm_month
    from arr_expansion a
),

expansion_components as (
    select
        p.period,
        sum(case when c.crm_month between p.period_start and p.period_end and c.deal_type = 'Expansion'
                 then c.crm_acv else 0 end) as crm_expansion_acv,
        sum(case when c.crm_month between p.period_start and p.period_end and c.deal_type = 'Renewal Uplift'
                 then c.crm_acv else 0 end) as crm_uplift_acv,
        sum(case when c.crm_month between p.period_start and p.period_end and c.classification = 'absorbed'
                 then c.crm_acv else 0 end) as absorbed_acv,
        sum(case when c.crm_month between p.period_start and p.period_end and c.classification = 'new_logo_month'
                 then c.crm_acv else 0 end) as new_logo_month_acv,
        sum(case when c.crm_month between p.period_start and p.period_end and c.classification = 'matched'
                      and c.matched_expansion_month > p.period_end
                 then c.crm_acv else 0 end) as timing_out_acv
    from periods p
    cross join crm_final c
    group by 1
),

expansion_timing_in as (
    select
        p.period,
        sum(case when a.arr_month between p.period_start and p.period_end
                      and a.matched_crm_month is not null and a.matched_crm_month < p.period_start
                 then a.movement_arr else 0 end) as timing_in_arr,
        sum(case when a.arr_month between p.period_start and p.period_end and a.matched_crm_month is null
                 then a.movement_arr else 0 end) as self_serve_expansion_arr
    from periods p
    cross join arr_final a
    group by 1
),

expansion_bridge as (
    select
        e.period, e.crm_expansion_acv, e.crm_uplift_acv, e.absorbed_acv, e.new_logo_month_acv,
        e.timing_out_acv, t.timing_in_arr, t.self_serve_expansion_arr,
        l.expansion_arr as landed_expansion_arr,
        (e.crm_expansion_acv + e.crm_uplift_acv - e.absorbed_acv - e.new_logo_month_acv
            - e.timing_out_acv + t.timing_in_arr + t.self_serve_expansion_arr) as implied_landed_arr,
        l.expansion_arr
            - (e.crm_expansion_acv + e.crm_uplift_acv - e.absorbed_acv - e.new_logo_month_acv
               - e.timing_out_acv + t.timing_in_arr + t.self_serve_expansion_arr)
            as unexplained_residual
    from expansion_components e
    join landed_arr_by_period l on l.period = e.period
    join expansion_timing_in t on t.period = e.period
),

expansion_rows as (
    select period, 'Expansion' as bridge_type, 1 as line_order, 'Closed-Won CRM Expansion ACV' as line_item, crm_expansion_acv as amount from expansion_bridge
    union all
    select period, 'Expansion', 2, 'Renewal uplift ACV (booked in CRM, lands in ARR as Expansion)', crm_uplift_acv from expansion_bridge
    union all
    select period, 'Expansion', 3, 'Absorbed into a non-Expansion net movement (offset by a simultaneous contraction)', -absorbed_acv from expansion_bridge
    union all
    select period, 'Expansion', 4, 'Recorded in the customer''s own New-Logo month (already in New Logo ARR)', -new_logo_month_acv from expansion_bridge
    union all
    select period, 'Expansion', 5, 'Activation timing: signed this period, lands later', -timing_out_acv from expansion_bridge
    union all
    select period, 'Expansion', 6, 'Activation timing: signed earlier period, lands this period', timing_in_arr from expansion_bridge
    union all
    select period, 'Expansion', 7, 'Self-serve / sub-threshold expansion (no matching CRM opportunity)', self_serve_expansion_arr from expansion_bridge
    union all
    select period, 'Expansion', 8, 'Landed Expansion ARR (fct_arr_waterfall)', landed_expansion_arr from expansion_bridge
    union all
    select period, 'Expansion', 9, 'Unexplained residual', unexplained_residual from expansion_bridge
),

-- ---------------------------------------------------------------------------
-- Combined (PHASE1_SPEC 8.8's own "new-logo plus expansion ARR" framing)
-- ---------------------------------------------------------------------------
combined_rows as (
    select
        n.period, 'Combined' as bridge_type, 1 as line_order,
        'Unexplained residual (New Logo + Expansion)' as line_item,
        n.unexplained_residual + x.unexplained_residual as amount
    from new_logo_bridge n
    join expansion_bridge x on x.period = n.period
    union all
    select
        n.period, 'Combined', 2, 'Period New ARR (New Logo + Expansion, tolerance base)',
        n.landed_new_logo_arr + x.landed_expansion_arr
    from new_logo_bridge n
    join expansion_bridge x on x.period = n.period
)

select period, bridge_type, line_order, line_item, amount from new_logo_rows
union all
select period, bridge_type, line_order, line_item, amount from expansion_rows
union all
select period, bridge_type, line_order, line_item, amount from combined_rows
order by period, bridge_type, line_order
