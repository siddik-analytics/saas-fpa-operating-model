-- Core dimension: one row per sales rep, all time (active and departed). Pass-through of
-- staging. Every rep is quota-carrying -- see stg_dim_sales_rep.
select *
from stg_dim_sales_rep
