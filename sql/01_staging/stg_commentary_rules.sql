-- Staging: typed pass-through of raw_commentary_rules, the DuckDB table
-- src/commentary_rules.py materialises from config/commentary_rules.yml (the same "config
-- drivers, not literals in SQL" convention every other phase follows). No business logic.
select
    category,
    key,
    cast(value_num as double) as value_num,
    value_text
from raw_commentary_rules
