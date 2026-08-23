# Data dictionary

Source tables produced by Phase 2 and written to `data/raw/`. Everything here is synthetic.

**Conventions**

- Dates are ISO `YYYY-MM-DD`. Every monthly fact table is keyed on a month-end date.
- Money is USD, unrounded, to two decimal places. There is no FX.
- Booleans are written `true` / `false`. Empty cells are nulls, not zeros.
- `fact_gl_actuals`, `fact_budget` and `fact_forecast` use **natural ledger signs**: expenses
  are positive (debits) and revenue is negative (credits). This is what a trial-balance
  export looks like, and downstream models are expected to handle the sign rather than have
  it pre-flipped for them.

---

## Two things to know before building on this data

**1. `fact_subscription_monthly` is sparse.** A customer has rows only in the months it was
live. A churned customer has no rows at all afterwards, and a reactivating customer has a gap.
There are no zero-ARR rows. Any model that lags customer ARR to classify movement must first
build a dense spine — cross join `dim_date` to the customer set — or `LAG` will silently
compare non-adjacent months and turn a churn plus a reactivation into an expansion.

**2. The first month is an opening balance.** The monthly fact tables carry
**2023-12-31** even though the reporting window opens in January 2024, because a waterfall
needs a prior month to lag against. Without it every customer would classify as a new logo in
January 2024. `dim_date.is_actual` marks the 30 reporting months only, so
`fact_subscription_monthly` spans 31 months and `fact_gl_actuals` spans 30.

---

## dim_customer

One row per customer in the reporting extract. Grain: **customer**. Primary key `customer_id`.

Scoped to customers live at any point from the opening balance month onward, which is what a
CRM extract taken for this reporting cycle would contain. Customers acquired in 2019–2023 whose
relationship ended before December 2023 are not present.

| Field | Type | Description |
|---|---|---|
| `customer_id` | text | `CUST-00001`. Primary key. |
| `customer_name` | text | Contractor-style trading name. Unique across the table. |
| `segment` | text | `SMB`, `Mid-Market`, `Enterprise`. Derived from `employee_count`, never from ARR. |
| `employee_count` | integer | Customer's own headcount. SMB < 50, Mid-Market 50–499, Enterprise 500+. |
| `region` | text | Sales territory. A descriptor, not an analytical dimension. |
| `acquisition_date` | date | Start date of the first contract. |
| `acquisition_channel` | text | Inbound organic / paid, outbound SDR, partner, trade show. |
| `initial_contract_type` | text | `monthly`, `annual`, `multi_year` at acquisition. |
| `journey_archetype` | text | Observed journey pattern. See the methodology note on `recent_new_logo`. |
| `account_owner_rep_id` | text | FK to `dim_sales_rep.rep_id`. The rep who closed the account. |
| `csm_id` | text | FK to `dim_employee.employee_id`. |
| `customer_status` | text | `Active` or `Churned` at the reporting date. |
| `churn_date` | date | Last day of service. Null while active. |
| `first_arr` | decimal | Net ACV of the first contract. The FY2025 new-logo ACV anchor is measured on this. |

## dim_product

Grain: **product**. Primary key `product_id`.

| Field | Type | Description |
|---|---|---|
| `product_id` | text | `PRD-CORE`, `PRD-DISPATCH`, `PRD-INSIGHTS`. |
| `product_name` | text | Helio Core, Helio Dispatch, Helio Insights. |
| `product_type` | text | `Platform` or `Add-on`. |
| `pricing_model` | text | Per seat, or usage-tiered with a committed minimum. |
| `list_price_monthly` | decimal | Per-seat list price in the base-year price book. Zero for Insights, which is priced on a committed tier by segment rather than per seat. |
| `is_core` | boolean | True for Helio Core. Every live customer carries it. |

## dim_date

Monthly calendar spine, January 2019 to December 2027. Grain: **month**. Primary key
`month_end_date`.

| Field | Type | Description |
|---|---|---|
| `month_end_date` | date | Last calendar day of the month. |
| `month_start_date` | date | First calendar day. |
| `fiscal_year` | integer | Calendar year; Helio's fiscal year is the calendar year. |
| `fiscal_quarter` | text | `2026Q2`. |
| `month_number` | integer | 1–12. |
| `is_quarter_end` | boolean | March, June, September, December. |
| `is_year_end` | boolean | December. |
| `is_actual` | boolean | True for the 30 reporting months, January 2024 to June 2026. |
| `is_forecast` | boolean | True after the reporting date. |

## fact_contract

One row per contract as executed. Grain: **contract**. Primary key `contract_id`.

Scoped to contracts in force during or after the opening balance month. A
`predecessor_contract_id` pointing outside the extract is set to null rather than left
dangling, so referential integrity holds on the committed files.

| Field | Type | Description |
|---|---|---|
| `contract_id` | text | `CTR-00417-02`. Primary key. |
| `customer_id` | text | FK to `dim_customer`. |
| `contract_type` | text | `monthly`, `annual`, `multi_year`. |
| `term_months` | integer | 1, 12, 24 or 36. Month-to-month commits to one month. |
| `start_date` | date | First day of service under this contract. |
| `end_date` | date | Last day of the committed term. For a rolling month-to-month agreement, the last day of service, or the reporting date if still live. |
| `renewal_date` | date | When the renewal was executed. On or a few days after `end_date`. Null for month-to-month, which has no anniversary and therefore never appears in a renewal base. |
| `billing_frequency` | text | Monthly in arrears, quarterly in advance, annual in advance. |
| `list_acv` | decimal | Annualised value at list, before discount. |
| `discount_pct` | decimal | Discount to list. Narrows at renewal as price rises toward list. |
| `net_acv` | decimal | Annualised contracted value net of discount. This is the ARR the contract carries. |
| `tcv` | decimal | Total contract value. A termed contract books its full committed value; a month-to-month agreement commits to nothing beyond the current month, so its TCV is measured over the service actually delivered. |
| `renewal_status` | text | `Active`, `Renewed`, `Churned`, `Early Termination`, `Rolling`. |
| `predecessor_contract_id` | text | The contract this one renewed from. Null on a first contract, a reactivation, or where the predecessor is outside the extract. |
| `uplift_pct_at_renewal` | decimal | Price uplift realised at renewal, 3–5%. Zero where the renewal was flat or the customer was contracting. Kept separate from seat and module growth so Phase 3 can attribute expansion to its cause. |

## fact_subscription_monthly

**Grain: customer × product × month.** Primary key `customer_id` + `product_id` +
`month_end_date`. The largest table, and the one the ARR engine is built on.

**This table stores state only.** There is no movement type, no new or expansion or churn
column, and there never will be. Movement classification happens in Phase 3 at customer-month
grain, after aggregating across products, because a customer moving $30k from Dispatch to Core
in one month is not a $30k expansion and a $30k contraction.

| Field | Type | Description |
|---|---|---|
| `customer_id` | text | FK to `dim_customer`. |
| `product_id` | text | FK to `dim_product`. |
| `contract_id` | text | FK to `fact_contract`. The contract in force at month end. |
| `month_end_date` | date | Month the state is measured at. |
| `seats` | integer | Licensed seats. Zero on Helio Insights, which is not sold per seat. |
| `mrr` | decimal | Monthly recurring revenue for this customer and product. |
| `arr` | decimal | `mrr × 12`, exactly, by construction. |

## fact_crm_opportunity

Grain: **opportunity**. Primary key `opportunity_id`.

The CRM is deliberately not a clean mirror of ARR. Every difference is one of the reconciling
items the Phase 5 CRM-to-ARR walk has to explain, and none of it is arbitrary noise.

| Field | Type | Description |
|---|---|---|
| `opportunity_id` | text | `OPP-001234`. Primary key. |
| `account_id` | text | The customer for a provisioned win or an expansion. A prospect id (`ACCT-P-…`) on losses and on wins that never provisioned. **Not a strict foreign key** — a CRM holds prospects that never became customers. |
| `segment` | text | Segment of the account or prospect. |
| `rep_id` | text | FK to `dim_sales_rep`. |
| `created_date` | date | Opportunity created. |
| `expected_close_date` | date | The rep's forecast close. Differs from actual; that gap is slippage. |
| `actual_close_date` | date | Close date. Null while open. |
| `stage` | text | Discovery, Qualification, Proposal, Negotiation, Closed Won, Closed Lost. |
| `stage_probability` | decimal | Stage weighting, 0.10 to 1.00. |
| `deal_type` | text | New Logo, Expansion, Renewal Uplift. |
| `contract_term_months` | integer | Term sold. |
| `pipeline_value` | decimal | ACV in the funnel. Coverage ratios are computed on this. |
| `acv` | decimal | Annual contract value. |
| `tcv` | decimal | Total contract value. Exceeds ACV on multi-year deals, which is a reconciling item: CRM records TCV, ARR records year-one ACV. |
| `status` | text | Won, Lost, Open. |
| `loss_reason` | text | Populated on every loss, null otherwise. |
| `lead_source` | text | Attribution channel. |
| `provisioned_flag` | boolean | False on roughly 3% of closed-won deals that never activated, and on all losses and open deals. |

**Built-in reconciling items.** Signature in one month and activation in the next on about
27% of wins; TCV against ACV on multi-year deals; wins that never provision; post-close
amendments that move ACV after the CRM record was frozen; and renewal uplift booked as an
opportunity but classified as expansion in ARR.

## dim_sales_rep

Grain: **rep**. Primary key `rep_id`. The same individuals appear in `dim_employee`, with
matching names and hire dates, so Sales headcount and rep counts cannot drift apart.

| Field | Type | Description |
|---|---|---|
| `rep_id` | text | `REP-014`. Primary key. |
| `rep_name` | text | Matches the corresponding `dim_employee.employee_name`. |
| `segment` | text | Segment the rep carries quota in. |
| `territory` | text | Assigned territory. |
| `hire_date` | date | Start date. Ramp is measured from here. |
| `termination_date` | date | Null if still employed at the reporting date. |
| `annual_quota` | decimal | $700k SMB, $1.0M Mid-Market, $1.4M Enterprise. |
| `ramp_profile_id` | text | `standard` or `enterprise`. |
| `commission_rate_new` | decimal | 9% on new-logo ACV. |
| `commission_rate_expansion` | decimal | 6% on expansion ACV. |
| `manager_id` | text | Segment sales manager. |

## fact_marketing_spend

Grain: **month × channel**. Primary key `month_end_date` + `channel`.

| Field | Type | Description |
|---|---|---|
| `month_end_date` | date | Month of spend. |
| `channel` | text | Paid search, paid social, content and SEO, trade shows and events, partner co-marketing, outbound programmes. |
| `spend` | decimal | Programme spend. Ties to accounts 6100, 6110 and 6120 in the ledger. |
| `opportunities_created` | integer | Opportunities sourced. |

The Q1 2026 demand-generation delay is visible here as a spend reduction across January to
March 2026. It is one of the drivers of the reforecast gap.

## dim_employee

Grain: **employee**. Primary key `employee_id`. Scoped to anyone employed during the
reporting window.

| Field | Type | Description |
|---|---|---|
| `employee_id` | text | `EMP-0142`. Primary key. |
| `employee_name` | text | |
| `department` | text | Operating cost-centre name, finer than `function`. |
| `function` | text | One of the eight reporting functions the headcount anchor is stated in. |
| `title` | text | |
| `level` | text | IC1–IC5, M1, M2, VP, C. |
| `hire_date` | date | |
| `termination_date` | date | Null if still employed. |
| `termination_type` | text | Voluntary or Involuntary. Null if still employed. |
| `annual_salary` | decimal | Current base salary. |
| `bonus_target_pct` | decimal | Zero for Sales, who carry commission instead. |
| `commission_eligible` | boolean | True for the Sales function. |
| `location` | text | Denver, remote US, or a satellite office. |
| `employee_type` | text | Full-time, Part-time, Contractor. |
| `cost_center` | text | `CC-3000`. Joins to `chart_of_accounts.yml`. |

**Headcount and FTE are different numbers.** 206 people are on the books at 30 June 2026 and
198 of them are FTE; the remaining 8 are part-time or contractor. Both figures appear in the
specification and both are reproduced here.

## fact_requisition

Grain: **requisition**. Primary key `req_id`. Scoped to requisitions approved from January
2025, which is what an applicant tracking export for the current planning cycle would hold.
Not every hire runs through the ATS.

| Field | Type | Description |
|---|---|---|
| `req_id` | text | `REQ-0042`. Primary key. |
| `department` | text | |
| `function` | text | |
| `title` | text | |
| `approved_date` | date | Requisition approved. |
| `planned_start_date` | date | Start date committed at approval. |
| `actual_start_date` | date | Actual start. Null while open or cancelled. The gap is hiring slippage. |
| `req_type` | text | New or Backfill. |
| `status` | text | Filled, Open, Cancelled. |
| `budgeted_salary` | decimal | Salary budgeted at approval. |
| `linked_employee_id` | text | FK to `dim_employee`. Null unless filled. |

Slippage is a generated driver, not a stated conclusion. Most requisitions start late and 2026
runs later than 2024–25, with a materially higher cancellation rate. The conditions for a
favourable compensation variance are present in the data; the analysis is Phase 6.

## fact_gl_actuals

Grain: **month × cost centre × account × category**. 30 months, January 2024 to June 2026.

| Field | Type | Description |
|---|---|---|
| `month_end_date` | date | Accounting period. |
| `cost_center` | text | `CC-3000`. Defined in `chart_of_accounts.yml`. |
| `department` | text | Cost-centre name. |
| `account_code` | text | One of 26 operating accounts. |
| `account_name` | text | Natural account name. |
| `account_category` | text | One of the seven approved P&L categories. |
| `actual_amount` | decimal | Natural ledger sign: expenses positive, revenue negative. |

A single natural account posts under many cost centres, which is how a real ledger is
organised. The P&L category is a function of the account **and** the cost centre, which is why
Customer Success payroll splits 60% to Subscription COGS and 40% to Sales & Marketing without
needing a duplicate account code. Statistical accounts (`9000`–`9300`) never post here.

## fact_budget and fact_forecast

Same shape, different version and horizon. Grain: **version × month × cost centre × account**.

| Field | Type | Description |
|---|---|---|
| `version` | text | `FY2026-Board-Approved` or `FY2026-Q2-Reforecast`. |
| `month_end_date` | date | Plan period. |
| `cost_center` | text | `CC-9000` on statistical rows. |
| `department` | text | |
| `account_code` | text | An operating account, or a `9xxx` statistical account. |
| `account_name` | text | |
| `account_category` | text | A P&L category, or `Memo - ARR` / `Memo - Statistical`. |
| `budget_amount` / `forecast_amount` | decimal | Planned amount, same sign convention as the ledger. |

`fact_budget` covers January to December 2026 and was locked in December 2025.
`fact_forecast` covers July 2026 to December 2027: the first half of FY2026 is closed, so the
reforecast starts from the ARR the business actually carried at 30 June 2026.

**Statistical accounts**, present only in the planning tables:

| Code | Name | Category |
|---|---|---|
| 9000 | Ending ARR | Memo - ARR |
| 9010 | New Logo ARR | Memo - ARR |
| 9020 | Expansion ARR | Memo - ARR |
| 9030 | Reactivation ARR | Memo - ARR |
| 9040 | Contraction ARR | Memo - ARR |
| 9050 | Churn ARR | Memo - ARR |
| 9100 | New Logos Added | Memo - Statistical |
| 9110 | Ending Logo Count | Memo - Statistical |
| 9200 | Ending Headcount | Memo - Statistical |
| 9300 | Ending Cash | Memo - Statistical |

Neither version's exit ARR is typed in. Each is the result of applying movement components to
the opening ARR the generated data actually carried, so the Phase 7 bridge will reconcile to
the source rather than to a number someone wrote down.

---

## Relationships

```text
dim_customer ──< fact_contract ──< fact_subscription_monthly >── dim_product
     │                                        │
     │                                        └── dim_date (month_end_date)
     ├──< fact_crm_opportunity >── dim_sales_rep ~~ dim_employee (same people)
     └── dim_employee (csm_id)

dim_employee ──< fact_requisition
             └──> fact_gl_actuals (payroll, via cost_center)

fact_gl_actuals, fact_budget, fact_forecast ── chart_of_accounts.yml (account, cost centre)
```

`fact_crm_opportunity.account_id` is intentionally not a strict foreign key: prospects that
never closed, and wins that never provisioned, do not exist in `dim_customer`. The validation
suite enforces the rule that actually matters — every **provisioned** win resolves to a real
customer.
