-- Staging: typed pass-through of dim_date. No business logic.
select
    cast(month_end_date as date)   as month_end_date,
    cast(month_start_date as date) as month_start_date,
    fiscal_year,
    fiscal_quarter,
    month_number,
    is_quarter_end,
    is_year_end,
    is_actual,
    is_forecast
from raw_dim_date
