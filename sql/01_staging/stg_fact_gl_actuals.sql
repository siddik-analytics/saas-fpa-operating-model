-- Staging: typed pass-through of fact_gl_actuals. No business logic.
--
-- Natural ledger signs are preserved here -- expenses positive (debits), revenue negative
-- (credits), per docs/data_dictionary.md -- and are flipped only where a downstream 05_gtm
-- model needs a positive revenue figure, never silently.
select
    cast(month_end_date as date) as month_end_date,
    cost_center,
    department,
    account_code,
    account_name,
    account_category,
    cast(actual_amount as decimal(18, 2)) as actual_amount
from raw_fact_gl_actuals
