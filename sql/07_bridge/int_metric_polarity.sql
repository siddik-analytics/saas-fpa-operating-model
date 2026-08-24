-- Centralised favorable/unfavorable direction per metric (config/commentary_rules.yml:
-- metric_polarity), so no downstream model re-derives it with an inline CASE statement.
-- 'contextual' metrics (ending_headcount) never get an automatic favorable/unfavorable label --
-- PHASE1_SPEC-analogous instruction: headcount variance is not automatically good or bad.
select key as metric, value_text as polarity
from stg_commentary_rules
where category = 'polarity'
