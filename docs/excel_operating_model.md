# The Excel FP&A operating model

**Phase 9.** `excel/Helio_SaaS_FP&A_Operating_Model.xlsx` — the financial-management interface
over the Phase 3–8 analytical stack. Every figure in it is generated from the committed marts by
`src/build_excel_model.py`; the generator's own output is validated by
`src/validate_excel_model.py` and `tests/test_excel_model.py`.

**Two workbooks, and the difference matters.** The builder writes
`build/generated/Helio_SaaS_FP&A_Operating_Model_generated.xlsx` — a build artefact, gitignored,
and the file the structural validator checks. The workbook committed at
`excel/Helio_SaaS_FP&A_Operating_Model.xlsx` is that generator output *after a six-phase
presentation review carried out in native Excel*: the Executive Summary was rebuilt around five
KPI cards and a hero chart, six charts were added from tables the build left unreferenced,
thirteen tables were demoted to a secondary weight, two duplicated blocks were deleted and every
sheet was brought inside a fixed effective-width ceiling. That work lives in the artefact, not in
the generator. **`python -m src.build_excel_model` does not reproduce the committed workbook
pixel for pixel, and no longer overwrites it.** What is reproducible is every number: the review
changed presentation only, and each phase was gated on an exhaustive scenario × output comparison
against the previous file with a largest absolute difference of exactly zero.

No VBA. No macros. No external links. No Power Query. No cloud dependency. No manual step after
the build. No password, so a reviewer can inspect every formula and every supporting table.

---

## How to review this workbook in 5 minutes

| # | Tab | What to look for | Time |
|---|---|---|---|
| 1 | **Executive Summary** | The dated header, the ten KPI tiles, the Budget-vs-Base table, the decision panel and the top five commentary items. This is the whole management problem on one screen. | 2 min |
| 2 | **Budget Bridge** | Four native Excel waterfalls walking Budget to Base for Exit ARR, Gross Profit, OpEx and Operating Income. Each has a visible residual line that reads zero. | 1 min |
| 3 | **GTM** | The first table. New Logo productive capacity, pipeline-supported bookings, and the constrained New Logo ARR that is the lesser of the two. Capacity alone does not equal achievable bookings. | 1 min |
| 4 | **Runway & Hiring** | Section A answers *can we afford it*, section B answers *is it worth it*. They point in different directions, and the tab says so. | 1 min |
| 5 | **Controls** | The overall status, the six upstream analytical controls, and eleven workbook-level checks. | 30 sec |

If you have one more minute: **Assumptions** shows every decision-driving input with its source
and its type, and marks management judgements in amber.

---

## 1. Purpose and audience

The workbook exists so that a recruiter, hiring manager, FP&A leader or CFO can open the project
and understand the business without reading SQL first. It answers one reporting cycle's
questions:

- Where does ARR land at Dec-2026, and why is that below the Board Budget?
- What is actually constraining New Logo ARR — sales capacity, or pipeline?
- Does the plan clear the Board's 24-month runway floor, and under which scenarios?
- Should Helio hire incremental sales capacity in H2 2026?
- Do the accounting mechanics beneath the commercial metrics hold together?

It is **not** a raw data dump and it is **not** a second forecast engine. Every business
calculation was already made and controlled in `sql/`; the workbook reads those results and
presents them.

## 2. Architecture

**Eleven visible tabs**, in reading order:

| # | Tab | Contents |
|---|---|---|
| 1 | Executive Summary | Dated header, 10 KPI tiles, Budget / Base / Variance table, management decision panel, top-5 deterministic commentary, 4 charts |
| 2 | ARR & Retention | Monthly ARR waterfall Jan-2025 → Dec-2026 with a visible actual/forecast split, TTM NRR / GRR / logo retention by segment, a segment panel, forward ATR by quarter |
| 3 | GTM | Capacity vs pipeline vs constrained New Logo ARR, sales capacity at the reporting date, win rate and cycle, pipeline coverage, FY2025 unit economics, sales efficiency |
| 4 | Forecast | The FY2026 monthly reforecast grid: ARR waterfall, P&L and headcount, Jan-26 through Dec-26, with a hard Actual / Reforecast column banner |
| 5 | P&L | Management P&L: FY2025 actual, H1 2026 actual, H2 2026 Base, FY2026 Base, FY2026 Budget, variance, variance %, favourable / unfavourable |
| 6 | Budget Bridge | Four Excel-native waterfalls with running balances and residuals, plus the gross-margin bps walk and the revenue bridge |
| 7 | Scenarios | Bear / Base / Bull comparison, the five management levers, a scenario-selector summary panel, 2 charts |
| 8 | Runway & Hiring | (A) affordability against the Board floor, (B) economic attractiveness on the FY2027 horizon, the Dec-2026 ramp snapshot shown separately, the full policy-runway table |
| 9 | Accounting | Bookings / billings / ARR / revenue kept apart, the deferred-revenue rollforward, the ASC 340-40 commission schedule, the forecast adjustment and its size |
| 10 | Assumptions | The decision-driving assumptions only, with value, unit, source and type |
| 11 | Controls | Overall status, six upstream controls, eleven workbook-level checks, the full commentary set |

**Nine supporting data sheets**, hidden but never `veryHidden` and never protected:
`Data_ARR`, `Data_Retention`, `Data_GTM`, `Data_PnL`, `Data_Bridge`, `Data_Scenario`,
`Data_Runway`, `Data_Accounting`, `Data_Commentary`. Right-click any tab and choose Unhide to
inspect them. Each holds one or more real Excel Tables, and every presentation formula reads
those tables by structured reference.

There is deliberately **no visible tab per SQL mart**. Thirty-two marts feed thirty-six Excel
Tables behind eleven presentation tabs.

## 3. Source marts

| Tab | Marts read |
|---|---|
| Executive Summary | `fct_management_variance`, `fct_arr_budget_bridge`, `fct_arr_forecast`, `fct_pnl_reforecast`, `fct_cash_runway_policy`, `fct_hiring_scenario`, `fct_new_logo_diagnosis`, `fct_scenario_monthly`, `fct_commentary_output` |
| ARR & Retention | `fct_arr_forecast`, `fct_arr_waterfall`, `fct_retention_ttm`, `fct_renewal_base` |
| GTM | `fct_sales_capacity`, `int_gtm_capacity_pipeline_forecast`, `fct_new_logo_diagnosis`, `fct_pipeline_snapshot`, `int_crm_opportunity_normalized`, `fct_unit_economics`, `fct_sales_efficiency` |
| Forecast | `fct_arr_forecast`, `fct_pnl_reforecast`, `fct_headcount_forecast` |
| P&L | `fct_pnl_reforecast`, `int_budget_reforecast_comparison`, `fct_gross_profit_bridge`, `fct_operating_income_bridge`, `fct_headcount_forecast` |
| Budget Bridge | `fct_arr_budget_bridge`, `fct_gross_profit_bridge`, `fct_opex_budget_bridge`, `fct_operating_income_bridge`, `fct_revenue_budget_bridge` |
| Scenarios | `fct_scenario_monthly`, `fct_cash_runway_policy`, `int_forecast_drivers` |
| Runway & Hiring | `fct_cash_runway_policy`, `fct_hiring_scenario`, `fct_new_logo_diagnosis` |
| Accounting | `fct_crm_bookings`, `fct_billings`, `fct_deferred_revenue`, `fct_revenue_accounting_reconciliation`, `fct_commission_asset`, `fct_accounting_enhanced_pnl` |
| Assumptions | `config/assumptions.yml`, `config/commentary_rules.yml`, `int_forecast_drivers`, `fct_cash_runway_policy` |
| Controls | `ctl_control_results.csv`, `fct_commentary_output` |

## 4. Build and refresh

```bash
python -m src.build_excel_model
```

Reads `data/marts/*.csv`, validates that every required file and column is present, builds the
workbook at `build/generated/Helio_SaaS_FP&A_Operating_Model_generated.xlsx`, and then runs the
full validation suite over it. `--skip-validation` builds without checking; `--marts` and `--out`
override the input and output paths.

It writes nowhere near `excel/`. The reviewed workbook that ships is placed there by hand and is
never a build output — running the build can no longer destroy it.

The generated workbook is also refreshed by the normal project build:

```bash
python -m src.build
```

which generates the source data, builds the analytical layer, runs the six controls, exports the
marts, **rebuilds the workbook and validates it**, then runs the test suite. A failed workbook
check exits non-zero, exactly like a failed control.

To refresh the generated workbook alone against the committed marts without regenerating
anything upstream, run `python -m src.build_excel_model`. To refresh the marts first,
`python -m src.run_sql`.

**Carrying a mart change through to the shipped workbook is a manual step**, and deliberately so:
the review layer cannot be replayed by a script. Rebuild, compare the generated figures against
the reviewed workbook, and apply the delta in Excel. `tests/test_excel_model.py` checks the
reviewed workbook for what must hold regardless — that it is present, that it opens, and that all
26 controls in it read PASS — but it cannot tell you the marts have moved underneath it.

The build **fails loudly**. A missing mart file, an empty mart or a missing column raises
`MartError` and no file is written. It never silently produces a blank tab.

### One additive upstream change

`src/run_sql.py` now writes `data/marts/ctl_control_results.csv` — the control roster, its phase
label and its violation count — because the analytical layer's control results previously
existed only inside `data/helio.duckdb`, which is not committed. `sql/manifest.yml` carries a
`phase` and a `label` on each control to support it. Both are presentation metadata: no SQL
model reads them, and a control still passes if and only if its query returns zero rows.

## 5. Which calculations live in SQL, and which live in Excel

**SQL owns every business calculation.** ARR movement classification, TTM retention cohorts and
the GRR cap, available-to-renew, sales capacity and ramp, the `LEAST(capacity, pipeline)` New
Logo constraint, every forecast driver, the bottom-up P&L build, the cash and Board-policy
runway, the computed hire counts, every Budget-to-Base bridge decomposition, materiality,
metric polarity, the deterministic commentary text, billings, the deferred-revenue rollforward
and the ASC 340-40 commission schedule.

**Excel owns presentation arithmetic only:**

| Excel does | Example |
|---|---|
| Variance and variance % | `=F12-G12`, `=IF(G12=0,"",F12/G12-1)` |
| Favourable / unfavourable from the Phase 7 polarity | `=LET(v,H12,p,XLOOKUP($B$12,tbl_pnl_summary[line_item],tbl_pnl_summary[polarity]),IF(p="contextual","n/a",…))` |
| Subtotals and margins on the forecast grid | `=D21+D22`, `=D27/D23`, `=SUM(D23:O23)` |
| Bridge running balances and the residual | `=D13+C14`, `=ROUND(C19-D18,2)` |
| Metric retrieval by structured reference | `=XLOOKUP("Exit ARR",tbl_mgmt_variance[metric_label],tbl_mgmt_variance[base_amount])` |
| Scenario and segment selection | `=XLOOKUP($C$38,tbl_scenario_summary[scenario],tbl_scenario_summary[dec_2026_exit_arr])` |
| Control aggregation | `=IF(SUM(tbl_controls[Violations])=0,"READY / PASS","FAIL")` |
| Identity checks visible on the sheet | the ARR waterfall check, the deferred-revenue rollforward residual |

Excel does **not** re-implement the SQL engine anywhere. Where the workbook shows an identity
check — the ARR waterfall on the Forecast and ARR & Retention tabs, the bridge residuals, the
deferred-revenue residual — that is a *check on the workbook*, computed over values the marts
already produced, not a second derivation of the number.

### Two aggregations that reproduce a published convention

`src/excel_data.py` sums two figures across a period rather than reading a stored annual total,
because no mart carries one. Both reproduce the method the Phase 5 validation report already
documents and publishes, and both are asserted against it:

- **FY2025 unit economics** — bookings and cost sum across the four quarters, then divide once
  (`reports/gtm_validation_report.md` section 7).
- **New Logo win rate and median sales cycle** — closed won against closed won plus closed lost,
  New Logo only, open pipeline excluded from the denominator
  (`reports/gtm_validation_report.md` section 5).

## 6. Formula philosophy

Compatibility target: **Microsoft 365**.

Used: Excel Tables and structured references, `XLOOKUP`, `SUMIFS`, `SUM`, `IF`, `IFERROR`,
`ROUND`. Every lookup is by name into a named table column, so inserting a row in a supporting
table cannot silently break a presentation formula.

`LET` is deliberately **not** used. It was, briefly, in the P&L favourable / unfavourable
formula, where it named the polarity lookup once instead of repeating it. `LET` declares a name,
and a declared name is a second OOXML namespace to get right on top of `_xlfn.` — see below.
That is a real interoperability risk to carry for a formula whose only job is to print one of
four words, and repeating an `XLOOKUP` against a fourteen-row table costs nothing. The
behaviour is unchanged; the formula is now plain nested `IF` over `XLOOKUP`.

Deliberately not used: `OFFSET`, `INDIRECT`, `NOW`, `TODAY`, `RAND` (volatile or non-deterministic),
entire-column `SUMPRODUCT`, deeply nested `IF` chains, and cross-sheet hard-coded cell
references. `src/validate_excel_model.py` asserts the absence of each banned function on every
build, so the constraint is enforced rather than merely intended.

### Modern functions and the `_xlfn.` namespace

Every worksheet function introduced after Excel 2007 is **stored in the file format under the
`_xlfn.` future-function namespace** — `_xlfn.XLOOKUP`, `_xlfn.LET` — and a few dynamic-array
functions under `_xlfn._xlws.` as well. Excel writes the prefix itself and hides it in the
formula bar, so a workbook saved by Excel shows `XLOOKUP(...)` on screen while the XML holds
`_xlfn.XLOOKUP(...)`.

**openpyxl does not do this.** It writes the formula string it is handed, verbatim, straight
into the `<f>` element. A bare `XLOOKUP(` therefore reaches Excel as an unrecognised defined
name, and every cell using it renders `#NAME?` the moment the workbook opens.

`excel_style.qualify_formula` closes that gap at the single point every cell is written, so no
formula in the workbook can bypass it. Substitution happens only outside string literals — a
lookup key or a commentary headline containing a function name is never touched — and the
transform is idempotent. `excel_style.MODERN_FUNCTIONS` is the roster, and it carries the
correct namespace per function rather than blanket-prefixing everything: `_xlfn.SUM` is just as
broken as a bare `XLOOKUP`.

### Declared names need a second namespace: `_xlpm.`

`_xlfn.` namespaces the name of a *function*. A name **declared by** `LET` or `LAMBDA` is stored
under a different namespace again — `_xlpm.` — and so is every reference to it inside that call.

Getting the first right and the second wrong is worse than getting both wrong, because it looks
fixed. `_xlfn.LET(v,H10,p,_xlfn.XLOOKUP(...),...)` has correct function names and bare parameter
names; Excel cannot resolve `v` or `p`, rejects the formula, and **drops the entire record**,
reporting on open:

```
Removed Records: Formula from /xl/worksheets/sheet5.xml part
```

That is precisely what happened to the fourteen P&L Fav / Unfav cells (`J10:J23`). The workbook
no longer ships any `LET`, so the situation cannot arise; `excel_style.qualify_formula`
nevertheless serializes declared names correctly — including nested `LET`, `LAMBDA`, and names
that also appear inside string literals — and the validator rejects a bare parameter anywhere in
the package.

The workbook stores **481 namespaced calls**, all `_xlfn.XLOOKUP`, across the ten presentation
sheets that carry formulas, with zero bare occurrences, zero `LET`, and zero declared names.
Section 11 covers how that is verified.

## 7. Interactivity

Two dropdowns, both narrow by design.

**Scenario selector** — Scenarios tab, one cell, `Bear / Base / Bull`. It drives exactly one
clearly-labelled panel, *Scenario summary panel*. Nothing else on that tab and nothing anywhere
else in the workbook changes with it. **Base remains the Board reforecast throughout.** The
workbook does not silently reshape itself under a reader who has clicked a dropdown.

**Segment selector** — ARR & Retention tab, `Total / SMB / Mid-Market / Enterprise`. It drives
one small panel of segment ARR, retention and forward ATR figures. Everything else on the tab is
company Total unless the row says otherwise.

Both are native Excel data validation. There are no form controls, no buttons and no VBA.

## 8. The design system

Every visual constant lives in `src/excel_style.py`. `build_excel_model.py` names tokens; it
contains no font size and no colour literal outside the shared palette.

**Type scale** — one family (Calibri) and ten sizes, each with a job:

| Token | Size | Used for |
|---|---:|---|
| `title` | 18 | The company name, row 1 of every tab |
| `subtitle` | 11 | What this tab is |
| `section` | 10.5 | Section headings |
| `kpi_value` | 16 | KPI card figures |
| `status` | 20 | The Controls overall-status band |
| `header` / `header_left` | 9 | Table header rows |
| `label` / `value` | 9.5 | Body text and figures |
| `subsection`, `label_muted` | 9 | Secondary labels, period bands |
| `note` | 8.5 | Explanatory notes under a heading |
| `source`, `meta` | 8 | Source lines, the build stamp |
| `kpi_label`, `kpi_note` | 7.5 | KPI card label and context |

A test asserts that no cell on a presentation tab uses a size outside this scale.

**Palette** — seven fills, no more: navy for header rows, blue for secondary headers, a pale
blue rule, a light card/subtotal band, a faint blue for actual periods, a faint amber for
forecast periods, and amber for assumption cells. Green and red appear only as *type* colour on
favourable / unfavourable variance and on the control status. No gradients, no decorative fills.

**Spacing** — row heights are explicit everywhere: 14pt body, 25pt table headers, 24/15/11.5 for
the title block, 6.5pt spacers between blocks. `finalise_sheet` runs over every presentation tab
at the end of the build and gives any row nobody thought about the compact body height, so a
stray 15pt default cannot break the rhythm.

**Page grid** — column A is a 1.8-wide margin on every tab and is never written to. Content
starts at column B. Where a tab carries charts, a 2-wide gutter separates the content block from
a band of uniform 10.5-wide chart columns. Titles, tables and charts therefore start on the same
left margin on all eleven tabs, and charts stack on a fixed 18-row rhythm.

**Tables** — a navy header row, thin separators rather than boxed borders, subtotals bold with a
top rule, totals on a light band, one-level indentation for detail lines under a subtotal, labels
left and figures right. Zero is `-`, negatives are in parentheses, and no management figure
carries cents.

**Charts** — twelve, on three standard sizes: `CHART_WIDE` (24 × 11 cm) for bridges and long
time series, `CHART_STANDARD` (19 × 10) and `CHART_COMPACT` (19 × 8). Sizes are verified from the
drawing XML rather than through openpyxl, which hands back its own default on reload. Titles 12pt
bold navy, axis and legend text 9.5pt grey, data labels 9pt, gridlines faint and horizontal only,
no chart border, no background fill, no built-in Excel chart style.

Every chart reads a purpose-built block on the hidden `Chart_Data` sheet — a text category
column and contiguous numeric series columns, stored values only, no formula and no blank rows.
`write_chart_block` returns a `ChartBlock` recording the sheet and columns it wrote, and the
chart helpers take that block rather than loose coordinates, so a chart cannot point at the right
rows on the wrong sheet. Charts are set to plot hidden data (`plotVisOnly = 0`); without it Excel
renders every chart sourced from a hidden sheet empty.

**Number conventions** — `$37.6M` and `25.6 mo` on management views, `$000` on detailed
schedules with the unit stated in the column header, `+429 bps` for margin variance, one decimal
on percentages, one decimal on fractional FTE.

## 9. Traceability

Every displayed management number resolves to one of three things: an approved mart value, a
supporting Excel Table holding approved mart values, or an Excel formula over approved values.

A small grey **`Source:`** note sits beneath every major table naming the mart or marts behind
it. Cells are not individually labelled — that would be clutter, not traceability. If you want
the number behind a number, unhide the relevant `Data_*` sheet: the tables there are the exact
mart extracts the presentation tabs read.

## 10. Controls

The Controls tab shows two layers.

**Upstream analytical controls**, one row per control, with its phase, what it enforces, its
violation count and its status:
`ctl_arr_reconciliation` (Phase 3), `ctl_retention_bounds` (Phase 4), `ctl_gtm_controls`
(Phase 5), `ctl_forecast_controls` (Phase 6), `ctl_bridge_commentary` (Phase 7),
`ctl_accounting_enhancements` (Phase 8). A control passes if and only if its query returns zero
rows.

The **overall status** is a formula, not a typed word:

```excel
=IF(SUM(tbl_controls[Violations])=0,"READY / PASS","FAIL")
```

It is structurally incapable of reading `READY / PASS` while any upstream control carries a
violation, and conditional formatting turns it red the moment it reads `FAIL`. The test suite
asserts the formula's shape, not just its current result.

**Workbook-level checks**: version, build timestamp, source reporting date, forecast cutover,
number of marts read, external links, macros, protection, the largest bridge residual against
the $1.00 tolerance, the largest deferred-revenue rollforward residual, and an explicit note on
formula recalculation. Every one is independently asserted by `src/validate_excel_model.py`.

## 11. Validation, and what Python can and cannot check

`src/validate_excel_model.py` runs 127 checks, in five families.

**Structural** — the file is a valid XLSX package; the eleven presentation sheets exist, in
order, visible; the nine data sheets exist, hidden and not `veryHidden`; no duplicate worksheet
name; all thirty-six required Excel Tables present; no `xl/externalLinks/` part; no VBA part; no
formula with an external-workbook reference; no `#REF!`; no banned or volatile function; no
stored Excel error value; every chart series resolves to a sheet that exists; no 3D chart; no
pie chart; the file is under 8 MB.

**OOXML function namespacing** — read out of the saved ZIP package rather than through openpyxl,
because the defect this guards against lives in what the writer produced, not in what Python
reports back. Every `<f>` element in every worksheet part is parsed, string literals are blanked
so a lookup key can never be read as a function call, and every function call is checked against
`excel_style.MODERN_FUNCTIONS` and `validate_excel_model.LEGACY_FUNCTIONS`. Four failure modes
are rejected: a modern function with no namespace, a modern function with the wrong namespace, a
namespace on a legacy function that does not take one, and a function in neither roster — an
unclassified name is failed rather than assumed safe, because that is exactly how a `#NAME?`
reaches a reviewer's screen. `XLOOKUP` and `LET` are additionally asserted by name. A fifth
check covers declared names: every `LET` / `LAMBDA` parameter, anywhere in the package, must
carry `_xlpm.`, because a bare one costs the whole formula record rather than one cell's
value.

**Formatting** — structural only, and explicitly not a judgement of whether the workbook
looks good. Gridlines off on every presentation tab, frozen panes and a print area on every tab,
column A left as the margin everywhere, the same title-block style on all eleven, no merged cells
anywhere in the workbook, one font family, every type size drawn from the scale, the ten KPI
cards identical in height and column position, every chart the house size, no chart carrying a
built-in Excel style, and no row left at Excel's default height. These catch the mechanical
regressions that make a workbook look wrong; they cannot tell you it looks right.

**Chart specification** — read from the saved package. Every chart must have a title, at
least one series, categories written as a *text* reference, every reference resolving to a real
sheet and a populated numeric range, matching category and value lengths, no `#REF!`, a supported
chart type, one of the three standard sizes, a size above the readable minimum, and a
`plotVisOnly` setting compatible with where its data lives. Four charts are additionally tied to
their marts by value: the Exit ARR bridge must open at Budget and close at Base, the scenario
chart must tie `fct_scenario_monthly`, the runway chart must tie `fct_cash_runway_policy` and
carry the 24-month floor, and the GTM chart must tie `fct_new_logo_diagnosis`.

**Value** — the Executive Summary KPIs, the scorecard, the P&L, the forecast grid, all four
bridges and their residuals, the scenario table and its levers, the policy runway, the hiring
decision, the deferred-revenue and commission rollforwards, the commentary text, the control
roster, the ARR and retention tables, the GTM constraint and the unit economics are each
recomputed in Python from the committed marts and compared to what the workbook stores.

### The formula limitation, stated plainly

**`openpyxl` does not calculate formulas.** A formula cell in this workbook holds a formula
string and **no cached result** — there is nothing for the validator to read back and compare,
and this document does not pretend otherwise. Excel COM automation is deliberately not required
for the normal build.

The gap is closed from both sides instead:

- the formula **string** is checked structurally — the right table, the right column, the right
  operand cells, no banned function; and
- the value the formula should produce is checked **independently**, by recomputing it in Python
  from the underlying mart and comparing that against the supporting data table the formula
  reads.

A broken lookup fails the structural check. A wrong number fails the value check. Neither claims
Excel has run. When you open the workbook, Excel performs a full recalculation on load — the
file is saved with `fullCalcOnLoad` set — and the displayed values are computed then.

## 12. Tests

`tests/test_excel_model.py`, 41 tests. The workbook is rebuilt from the committed marts into a
temporary directory and put through the full validation suite; the committed artifact in
`excel/` is put through the same suite, so a mart change that has not been followed by a
workbook rebuild fails in CI rather than being found by a reviewer.

Ten of the thirty-one cover Excel interoperability specifically, all reading the ZIP package
directly rather than asking openpyxl what a formula says. Function namespacing: `XLOOKUP` is
namespaced in the worksheet XML; every function in `MODERN_FUNCTIONS` carries its required
namespace; no formula across all 668 uses a name Excel will not recognise; and the guard is
**mutation-tested** by stripping every `_xlfn.` from the saved package and requiring validation
to reject it. Declared names: `sheet5.xml` is confirmed to be the P&L worksheet by the
workbook's own sheet order; all fourteen Fav / Unfav formulas are confirmed present, namespaced
and free of `LET`; no declared name anywhere lacks `_xlpm.`; that guard is **mutation-tested**
too, by rebuilding the exact broken formula the P&L used to carry and requiring the validator to
catch it; and the `_xlpm.` serializer has direct unit coverage for nesting, `LABMDA` and string
literals. A check that never fails proves nothing, so both guards are made to fail on demand.

Excel recalculation is asserted separately: `fullCalcOnLoad="1"` must be present in
`xl/workbook.xml`. Beyond that: sheet inventory
and order, hidden-sheet accessibility, external links and macros, banned functions, the
executive scorecard against `fct_management_variance`, the Exit ARR waterfall against Phase 7,
the P&L against Phase 6, scenarios against `fct_scenario_monthly`, policy runway against
`fct_cash_runway_policy`, hiring against `fct_hiring_scenario` on the Dec-2027 horizon,
accounting against Phase 8, commentary provenance, the control status formula's structure, the
variance formulas' structure, the GTM `LEAST()` relationship, the Jun-2026 cutover, that a
missing mart raises rather than producing a blank workbook, and that generating the workbook
modifies no upstream mart.

## 13. Limitations

1. **No cached formula results.** See section 11. Formula *values* are verified against the
   marts in Python, not read back out of the file. This is a separate question from formula
   *serialization*: section 6 covers the `_xlfn.` and `_xlpm.` namespacing that makes the
   formulas resolvable by Excel in the first place, and that is verified against the saved XML.
2. **Automated checks do not substitute for opening the file.** Everything here is verified
   against the marts and against the saved OOXML, but neither Python nor pytest runs Excel's
   own parser. **A manual reopen in Microsoft Excel is required to confirm no recovery dialog
   and no `#NAME?` errors.**
3. **The workbook is a read layer.** It cannot change a driver and re-forecast. Changing an
   assumption means editing `config/assumptions.yml` and rebuilding the analytical layer, which
   is the point: the assumptions are version-controlled, not buried in a spreadsheet cell.
4. **The scenario selector drives one panel only.** By design — see section 7 — but it does mean
   the charts and tables elsewhere on the Scenarios tab always show all three scenarios rather
   than the selected one.
5. **Two runway figures exist upstream, and only one is used for affordability.** The
   Board-policy runway (`fct_cash_runway_policy`) answers the 24-month floor question. The
   model-derived operating cash proxy is a relative-comparison tool and is not presented as a
   governance conclusion anywhere in the workbook.
6. **Segment-level Budget ARR figures are allocations.** `fact_budget` carries no segment grain
   for ARR movements, so the Budget side of any segment ARR bridge is allocated and is labelled
   `budget_grain = 'allocated'` in `tbl_arr_bridge_segment`. Base's segment figures are always
   segment-native.
7. **Budget carries no functional headcount grain.** The P&L tab's by-function headcount table
   therefore has no Budget column, rather than a fabricated departmental split.
8. **The commission asset is analytically derived, not GL-reconciled.** `fact_gl_actuals` is a
   P&L extract with no balance sheet. The Accounting tab says so on the sheet.
9. **Accounting billings and deferred revenue are shown for actual periods only.** The contract
   billing schedule stops at the reporting date; no forecast billings series is invented.
10. **`fct_hiring_scenario` spans Jul-2026 to Dec-2027**, so the hiring tab's horizon is fixed by
   the mart, not chosen here.
11. **Mart exports are not byte-stable across rebuilds.** `src/run_sql.py` orders each mart
    export by its first two columns, so rows tied on those two columns can be emitted in a
    different order, and DuckDB's parallel aggregation moves the last digit or two of some
    floating-point values. This predates Phase 9 and affects the CSVs, not the workbook: every
    workbook figure is compared to the marts on tolerances far wider than that dust. It does
    mean a full `python -m src.build` produces a cosmetically different `data/marts/` diff even
    when nothing has changed.
12. **PHASE1_SPEC section 10 names a five-tab workbook at `models/Helio_FPA_Operating_Model.xlsx`.**
    This phase builds eleven visible tabs (fourteen after the presentation review) at
    `excel/Helio_SaaS_FP&A_Operating_Model.xlsx`,
    following the Phase 9 brief. Recorded here as a deviation from the frozen specification
    rather than left as a silent difference — the same convention
    `docs/gtm_finance.md` uses for its own PHASE1_SPEC 8.5 deviation.

---

## Related documentation

- [ARR engine](arr_engine.md) · [Retention and renewals](retention_renewals.md) ·
  [GTM finance](gtm_finance.md) · [Forecast, scenarios and runway](forecast_runway.md) ·
  [Bridges and commentary](bridge_commentary.md) ·
  [Accounting enhancements](accounting_enhancements.md)
- [PHASE1_SPEC](PHASE1_SPEC.md) — the frozen design this build implements.
