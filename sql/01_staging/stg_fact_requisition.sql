-- Staging: typed pass-through of fact_requisition. No business logic.
--
-- Loaded for the first time in Phase 6: the headcount forecast's known-hire signal (an OPEN
-- requisition is a hire that has already been approved, not a hypothetical). actual_start_date
-- and linked_employee_id are null for every Open or Cancelled row (docs/data_dictionary.md).
select
    req_id,
    department,
    function,
    title,
    cast(approved_date as date) as approved_date,
    cast(planned_start_date as date) as planned_start_date,
    cast(actual_start_date as date) as actual_start_date,
    req_type,
    status,
    cast(budgeted_salary as decimal(18, 2)) as budgeted_salary,
    linked_employee_id
from raw_fact_requisition
