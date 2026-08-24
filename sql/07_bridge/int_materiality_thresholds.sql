-- Centralised materiality thresholds (config/commentary_rules.yml: materiality), long/tidy:
-- one row per (metric, threshold_name). threshold_name in ('abs_usd', 'pct', 'bps', 'fte',
-- 'months'). A metric is material if it clears ANY threshold defined for it -- see
-- fct_management_variance, which is the only model that applies these.
select
    split_part(key, '::', 1) as metric,
    split_part(key, '::', 2) as threshold_name,
    value_num as threshold_value
from stg_commentary_rules
where category = 'materiality'
