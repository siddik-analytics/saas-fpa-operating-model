-- Core dimension: one row per customer. Pass-through of staging; kept as its own model so
-- later phases (retention, GTM) can add conformed attributes without touching staging.
select *
from stg_dim_customer
