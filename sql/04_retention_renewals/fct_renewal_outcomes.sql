-- Historical renewal outcomes (PHASE1_SPEC 8.3, section 9): what actually happened the last
-- time each resolved contract came up for renewal. Backward-looking by construction -- see
-- int_contract_renewal_event and docs/retention_renewals.md for the distinction from
-- fct_renewal_base, which is forward-looking and does not yet know an outcome:
--
--   GRR / NRR (fct_retention_ttm)   = backward-looking customer retention result
--   ATR x expected renewal rate     = forward-looking renewal forecast basis
--
-- Renewal price uplift is isolated using fact_contract.uplift_pct_at_renewal applied to the
-- customer's own pre-renewal ARR, per the binding instruction to "use
-- fact_contract.uplift_pct_at_renewal and contract lineage." Whatever ARR change is left over
-- after removing the price effect is attributed to seat and module growth (or reduction) --
-- seat_module_arr is not itself re-priced, so it can be negative even on a contract that
-- nominally renewed with uplift, if seats were cut hard enough to outweigh the price rise.
--
-- renewal_outcome uses the net ARR direction at the renewal (PHASE1_SPEC section 9's own
-- category names), which is not the same split as price vs. seat/module -- a contract can be
-- "Renewed with Uplift" on net ARR while price_uplift_arr is a small part of that growth and
-- seat_module_arr the larger part, or vice versa. Both views are exposed so neither is implied
-- by the other.
select
    contract_id,
    customer_id,
    segment,
    contract_type,
    renewal_date,
    contract_end_date,
    outcome_month,
    successor_contract_id,
    renewal_status,
    pre_renewal_arr as atr_arr,
    post_renewal_arr as renewed_arr,
    case
        when renewal_status in ('Churned', 'Early Termination') then 0.0
        else coalesce(successor_uplift_pct, 0) * pre_renewal_arr
    end as price_uplift_arr,
    case
        when renewal_status in ('Churned', 'Early Termination') then 0.0
        else (post_renewal_arr - pre_renewal_arr) - coalesce(successor_uplift_pct, 0) * pre_renewal_arr
    end as seat_module_arr,
    case
        when renewal_status = 'Churned' then 'Churned'
        when renewal_status = 'Early Termination' then 'Early Termination'
        when post_renewal_arr > pre_renewal_arr then 'Renewed with Uplift'
        when post_renewal_arr < pre_renewal_arr then 'Renewed with Contraction'
        else 'Renewed'
    end as renewal_outcome,
    renewal_date - contract_end_date as renewal_lag_days
from int_contract_renewal_event
order by outcome_month, segment, contract_id
