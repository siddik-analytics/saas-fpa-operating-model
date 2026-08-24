-- Centralised commentary-wording and priority parameters (config/commentary_rules.yml:
-- commentary, priority) -- the "primarily" / "offset" / priority thresholds the commentary
-- engine reads instead of a hardcoded number in Python or SQL.
select key as param, value_num as value
from stg_commentary_rules
where category in ('commentary_param', 'priority_param')
