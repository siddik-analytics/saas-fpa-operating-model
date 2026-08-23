-- Staging: typed pass-through of dim_employee. No business logic.
--
-- Loaded from Phase 5 onward. Used by the GTM cost-allocation layer for cost-centre metadata
-- (function, department) via fact_gl_actuals' cost_center; individual employee rows are not
-- joined into the allocation itself (payroll is already aggregated in the ledger).
select
    employee_id,
    employee_name,
    department,
    function,
    title,
    level,
    cast(hire_date as date)        as hire_date,
    cast(termination_date as date) as termination_date,
    termination_type,
    cast(annual_salary as decimal(18, 2))   as annual_salary,
    cast(bonus_target_pct as decimal(9, 4)) as bonus_target_pct,
    cast(commission_eligible as boolean)    as commission_eligible,
    location,
    employee_type,
    cost_center
from raw_dim_employee
