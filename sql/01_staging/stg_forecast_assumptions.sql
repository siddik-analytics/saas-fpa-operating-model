-- Staging: typed pass-through of raw_forecast_assumptions, the DuckDB table
-- src/forecast_assumptions.py materialises from config/assumptions.yml: forecast (the same
-- "config drivers, not literals in SQL" convention every other phase follows). No business logic.
select
    category,
    driver,
    scenario,
    segment,
    cast(value as double) as value,
    unit,
    source_type,
    note
from raw_forecast_assumptions
