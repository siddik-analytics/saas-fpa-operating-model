# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v0.8] - Excel FP&A operating model

Phase 9a of the build described in `docs/PHASE1_SPEC.md`. Adds
`excel/Helio_SaaS_FP&A_Operating_Model.xlsx` - the financial-management interface over the frozen
Phase 3-8 analytical stack, generated reproducibly from the committed marts.

The workbook is a **read and present layer**. Every business calculation stays in `sql/`; Excel
does variance, variance %, favourable / unfavourable from the Phase 7 centralised metric
polarity, subtotals, bridge running balances, `XLOOKUP` retrieval and the control roll-up. No
Phase 2-8 model, control, mart or output is altered, and a test asserts that generating the
workbook modifies no upstream mart.

No VBA. No macros. No external links. No Power Query. No cloud dependency. No manual step after
the build. No workbook or worksheet protection, so a reviewer can inspect every formula and
every supporting table.

### Added

**The workbook** - `excel/Helio_SaaS_FP&A_Operating_Model.xlsx` (139 KB)
- Eleven visible presentation tabs: Executive Summary, ARR & Retention, GTM, Forecast, P&L,
  Budget Bridge, Scenarios, Runway & Hiring, Accounting, Assumptions, Controls.
- Nine hidden supporting data sheets (`Data_ARR`, `Data_Retention`, `Data_GTM`, `Data_PnL`,
  `Data_Bridge`, `Data_Scenario`, `Data_Runway`, `Data_Accounting`, `Data_Commentary`) holding
  36 real Excel Tables. Hidden, never `veryHidden`, never protected - right-click any tab and
  choose Unhide to inspect every table the presentation formulas read.
- 668 formula cells, 16 charts, 32 source marts. Deliberately no visible tab per SQL mart.
- **Executive Summary** - dated header, ten KPI tiles (Jun-26 ARR actual, Dec-26 Budget ARR,
  Dec-26 Base reforecast ARR, ARR variance, FY2026 revenue, gross margin, operating loss, ending
  headcount, Base Board-policy runway, Board floor), a Budget / Base / Variance table, a
  management decision panel in which every value and every verdict is a formula over an approved
  mart, the top five deterministic commentary items in Phase 7's own priority-then-materiality
  order, and four charts (the Exit ARR waterfall, Budget vs Base headline metrics, Bear / Base /
  Bull Dec-26 Exit ARR, and Board-policy runway against the 24-month floor).
- **Budget Bridge** - four Excel-native waterfalls (Exit ARR, Gross Profit, Total OpEx,
  Operating Income), each with an Excel-computed running balance and a visible residual line
  that reads zero against the $1.00 Phase 7 tolerance, plus the gross-margin basis-point walk
  and the revenue recognition-mechanic decomposition.
- **GTM** - New Logo productive capacity against pipeline-supported bookings against the
  constrained New Logo ARR that is the lesser of the two, with the binding constraint and the
  pipeline-bound segment-month count. The misleading blended-capacity-versus-New-Logo-target
  comparison that Phase 5 corrected is not reintroduced; blended capacity is shown for context
  only and never compared to that target.
- **Runway & Hiring** - affordability against the Board's 24-month floor and economic
  attractiveness on the Dec-2027 fuller-ramp horizon presented as two separate sections. The
  Dec-2026 figures are carried below, explicitly labelled a near-term ramp snapshot, because
  hires start 31 Oct 2026. Affordability uses the Board-policy runway only; the model-derived
  operating cash proxy is not quoted as a governance conclusion anywhere.
- **Controls** - the six upstream controls with their phase, what each enforces, violation count
  and status; eleven workbook-level checks; and an overall status that is a formula over the
  violation counts (`=IF(SUM(tbl_controls[Violations])=0,"READY / PASS","FAIL")`), structurally
  incapable of reading PASS while any upstream control carries a violation.
- Interactivity is limited to two native data-validation dropdowns: a Bear / Base / Bull scenario
  selector driving one clearly-labelled panel on the Scenarios tab, and a segment selector
  driving one panel on ARR & Retention. Base remains the Board reforecast everywhere else. No
  form controls, no buttons, no VBA.

**Workbook builder** - `src/build_excel_model.py`, `src/excel_data.py`, `src/excel_style.py`
- `excel_data.py` reads and reshapes the committed marts and derives nothing the analytical layer
  has not already decided. Two aggregations reproduce a published Phase 5 convention rather than
  inventing one - FY2025 unit economics (period-summed, then divided once) and the New Logo win
  rate and median sales cycle - and both are asserted against the published figures.
- `excel_style.py` holds the presentation vocabulary: one font, one restrained finance palette,
  one set of number formats, and the helpers that write a cell, a section, a KPI tile, an Excel
  Table or a chart. `resolve_format` rejects an unknown format token rather than writing it to
  the cell verbatim, where a token containing `d`, `m`, `y`, `h` or `s` would be read by Excel as
  a date pattern.
- The build fails loudly. A missing mart file, an empty mart or a missing column raises
  `MartError` and no file is written; it never produces a blank tab.

**Workbook validation** - `src/validate_excel_model.py`, 100 checks
- Structural: valid XLSX package, sheet inventory / order / visibility, no duplicate worksheet
  name, all 36 required Excel Tables present, no `xl/externalLinks/` part, no VBA part, no
  external-workbook formula reference, no `#REF!`, no banned or volatile function
  (`OFFSET`, `INDIRECT`, `NOW`, `TODAY`, `RAND`), no stored Excel error value, every chart series
  resolves to a sheet that exists, no 3D chart, no pie chart, file under 8 MB.
- OOXML serialization, read out of the saved ZIP package rather than through openpyxl: every
  modern function carries its required `_xlfn.` / `_xlfn._xlws.` namespace, no legacy function
  carries one it does not take, every function used is classified, and every name declared by
  `LET` or `LAMBDA` carries `_xlpm.`. See **Fixed**.
- Value: the Executive Summary KPIs and scorecard, the P&L, the forecast grid, all four bridges
  and their residuals, the scenario table and its five levers, the policy runway, the hiring
  decision on the Dec-2027 horizon, the deferred-revenue and commission-asset rollforwards, the
  commentary text, the control roster, the ARR and retention tables, the GTM `LEAST()`
  relationship and the FY2025 unit economics, each recomputed in Python from the committed marts
  and compared against what the workbook stores.
- **The formula limitation is handled explicitly rather than implied away.** `openpyxl` does not
  calculate, so no formula cell carries a cached result and nothing claims Python recalculated
  the workbook. Formula *strings* are validated structurally and the values they should produce
  are validated independently against the marts. Excel COM automation is not required for the
  normal build; the workbook is saved with full-calculation-on-load so Excel computes on open.

**Tests** - `tests/test_excel_model.py`, 31 tests
- The workbook is rebuilt from the committed marts into a temporary directory and put through
  the full validation suite, and the committed artifact in `excel/` is put through the same
  suite - so a mart change not followed by a workbook rebuild fails here rather than being found
  by a reviewer.
- Ten tests cover Excel interoperability, all reading the ZIP package directly rather than
  asking openpyxl what the formula says, including two mutation tests: one strips every `_xlfn.`
  prefix from the saved package, the other reconstructs the bare-parameter `LET` that Excel
  rejected, and validation must reject both.

**Documentation** - `docs/excel_operating_model.md`
- Purpose and audience, tab architecture, source marts per tab, the build and refresh process,
  which calculations live in SQL versus Excel, the scenario selector, formula philosophy,
  the formatting standard, traceability, controls, the validation approach and eleven stated
  limitations. Opens with a **"How to review this workbook in 5 minutes"** route.

### Changed -- visual design remediation

The workbook was analytically correct but visually weak. This pass makes it look like an
internal FP&A model rather than a generated spreadsheet. **No calculation, formula, mart,
business rule, control or architectural decision changed**; the 668 formulas and every displayed
value are the same, and all six upstream controls still pass.

**A design system, centralised in `src/excel_style.py`** (brief item 16). Twenty text tokens
covering title, subtitle, section, subsection, table header, body, KPI label, KPI value, note
and source; a `Rows` class of explicit row heights; the page grid (margin, content start,
gutter, chart band); and one chart size. `cell(..., style="...")` resolves a token, so
`build_excel_model.py` no longer carries a single font size or ad-hoc colour -- the six remaining
palette references are semantic (actual / forecast band ink, operating-income emphasis, input-cell
ink, PASS / FAIL) and each is paired with a token. A test asserts no cell uses a size outside the
scale.

**Executive Summary** rebuilt on a ten-column grid. Ten KPI cards, all identical in height and
column position, one per column with a gutter between so text overflows into its own empty
space rather than being clipped. Scorecard compacted to one line per metric with the period on
the label. Decision panel and commentary given real table structure instead of text dropped into
cells. Four charts stacked on a fixed 18-row rhythm in a dedicated band.

**P&L** given four blocks -- revenue, gross profit, operating expense, operating income -- with a
thin rule and a half-height spacer between each. Subtotals bold with a top rule, totals on a
light band, operating income emphasised in navy, one-level indentation for detail lines. The
variance group is set off by a left rule so Budget / Base reads as one block and the comparison
as another. Figures now in `$000` with the unit in the column header.

**Forecast** actual / reforecast distinction moved to a banner row plus a faint tint on the
reforecast columns only -- previously every data cell in both halves was filled, which turned the
grid into wallpaper. Detail in `$000`.

**Runway & Hiring** sections A and B given deliberately different heading accents so
affordability and attractiveness read as two questions. **Controls** overall status widened into
a band whose fill and type colour both come from its own formula -- green on READY / PASS, red on
FAIL. **Accounting** section headings lightened so the schedules read as supporting rather than
headline. **Charts** standardised: 17.4 x 8.6 cm, 10pt bold navy titles, 8pt grey axis and legend
text, faint horizontal gridlines only, no border, no fill, no built-in Excel chart style, angled
category labels on the bridge waterfalls.

**Every presentation tab** now shares the page grid: a 1.8-wide margin in column A that is never
written to, content from column B, gridlines off, frozen panes, a print area, and explicit row
heights on every used row via a `finalise_sheet` pass.

### Added -- formatting validation

Fourteen checks (100 -> 114) and six tests (31 -> 37), all structural: gridlines off, frozen
panes, print areas, margin column untouched and uniform, consistent title-block style, no merged
cells, one font family, every type size on the scale, KPI cards identical in height and column
position, no chart anchored outside the grid, no built-in Excel chart style, no row at Excel's
default height, and chart size read from the drawing XML.

That last one caught a weak check of my own: the previous chart-size assertion read
`chart.width` from a reloaded workbook, but openpyxl does not restore it and hands back its own
default, so the check passed regardless of what was written. It now reads `<ext cx cy>` from the
saved drawing XML.

**These checks do not judge whether the workbook looks good.** They catch the mechanical
regressions that make it look wrong. **Final acceptance requires manual visual review in
Microsoft Excel.**

### Fixed -- charts were empty or unreadable in Microsoft Excel

Reported after visual inspection: some charts completely empty, others with unreadable labels.
Two independent root causes, neither visible from Python -- openpyxl created sixteen valid chart
objects, and Excel could render almost none of them.

**Cause 1 -- every waterfall referenced the wrong worksheet.** `waterfall_chart()` built its
`Reference` objects against the *presentation* worksheet it was drawing on, while the row and
column coordinates it was given belonged to `Data_Bridge`. The five bridge charts therefore
pointed at empty cells on `Executive Summary` and `Budget Bridge`. Confirmed in the saved
package: `<cat><numRef><f>'Executive Summary'!$B$2:$B$9</f></numRef></cat>` on a chart whose
data lives on `Data_Bridge`. Completely empty in Excel.

**Cause 2 -- `plotVisOnly val="1"` on all sixteen charts, every source on a hidden sheet.** That
setting tells Excel to plot visible cells only; every chart in this workbook reads a hidden
`Data_*` sheet. Now `0` on every chart, which is what allows a chart to render from a hidden
source. The hidden sheets stay hidden.

**Cause 3 -- categories emitted as `numRef`.** openpyxl's `set_categories` always writes a
number reference, so text category labels came back to Excel as numbers and the axis rendered
1, 2, 3. Categories are now written as `strRef`.

**A dedicated chart-data layer.** A new hidden `Chart_Data` sheet holds one purpose-built block
per chart: a text category column, contiguous numeric series columns, stored values only, no
formula for Excel to calculate and no blank rows in the middle. `write_chart_block` returns a
`ChartBlock` recording the sheet and the exact columns it wrote, and the chart helpers take the
block rather than loose coordinates -- so a chart can no longer point at the right rows on the
wrong sheet. This adds no calculation; every figure already existed in a mart.

**Sixteen charts cut to twelve.** Removed: the TTM retention line chart (three metrics across
four segments is unreadable at any size, and the compact table above it communicates better);
the forward-ATR bar chart (six rows of quarters already show the seasonality); the scenario
runway bar (the same four bars as the Executive Summary chart); and the deferred-revenue bar
(the Accounting tab is meant to stay visually secondary). The Exit ARR bridge appears on both
the Executive Summary and the Budget Bridge tab -- the one deliberate repeat, because it is the
lead executive visual and also belongs with its three siblings.

**Readability.** Three named sizes replace the single 17.4 x 8.6 cm: `CHART_WIDE` (24 x 11),
`CHART_STANDARD` (19 x 10), `CHART_COMPACT` (19 x 8). Titles 12pt, axis and legend text 9.5pt,
data labels 9pt -- up from 10pt and 8pt. Monthly series use quarter-spaced tick labels
(`tickLblSkip`) while keeping every data point. Waterfall movements of zero are written as
blanks rather than 0.0, so no bar and no data label is drawn for them. Bridge category labels
are shortened ("New Logo ARR variance" to "New Logo") and angled. The Budget vs Base chart now
carries only monetary metrics -- Gross Margin (bps), Ending Headcount (FTE) and runway (months)
were sharing a dollar axis and have been removed from it.

### Added -- chart-spec validation

Thirteen checks (114 -> 127) and five tests (37 -> 41). Every chart: title present, at least one
series, categories are a text reference, every reference resolves to a real sheet and a
populated numeric range, category and value lengths agree, no `#REF!`, supported chart type only,
one of the three standard sizes, above the minimum readable size, and `plotVisOnly` compatible
with the source's visibility. Plus value ties: the Exit ARR bridge must open at Budget and close
at Base Exit ARR from Phase 7; the scenario chart must tie `fct_scenario_monthly`; the runway
chart must tie `fct_cash_runway_policy` and carry the 24-month floor; the GTM chart must tie
`fct_new_logo_diagnosis` on all three series.

**Mutation-tested, eight ways:** plotVisOnly reverted to 1, a series repointed at a presentation
sheet, a series repointed at a non-existent sheet, categories reverted to numRef, category and
value lengths made to disagree, `#REF!` injected, a title emptied, and a chart shrunk below the
readable minimum. All eight are caught. One of these found a defect in the validator itself --
an unresolvable reference made a tie check raise instead of fail, which would have reported
nothing at all on a broken workbook; it now degrades to a recorded failure.

**Manual Microsoft Excel visual inspection required.**

### Fixed

**Microsoft Excel removed the P&L formula records on open: "Removed Records: Formula from
/xl/worksheets/sheet5.xml part".**

*Which cells.* `P&L!J10:J23` - the fourteen favourable / unfavourable cells, one per P&L line.
Every other formula on that worksheet, and on the other ten, was accepted; sheet5 was the only
worksheet carrying a `LET`.

*As generated by the builder:*

```
=LET(v,H10,p,XLOOKUP($B$10,tbl_pnl_summary[line_item],tbl_pnl_summary[polarity]),
     IF(p="contextual","n/a",IF(v=0,"-",
     IF((p="higher_favorable")=(v>0),"Favorable","Unfavorable"))))
```

*As serialized in sheet5.xml, after the first namespacing fix:*

```
_xlfn.LET(v,H10,p,_xlfn.XLOOKUP($B$10,tbl_pnl_summary[line_item],tbl_pnl_summary[polarity]),
          IF(p="contextual","n/a",IF(v=0,"-",
          IF((p="higher_favorable")=(v>0),"Favorable","Unfavorable"))))
```

*Root cause - a second, different namespace.* `_xlfn.` namespaces the name of a FUNCTION. A name
DECLARED by `LET` or `LAMBDA` is stored under `_xlpm.` (Excel parameter), and so is every
reference to it inside that call. The first fix namespaced the function names correctly and left
the declared names `v` and `p` bare. Excel could not resolve them, rejected the formula, and
dropped the entire record - which is reported as a removed record rather than as a `#NAME?`,
because the formula never survives parsing to be evaluated. Getting `_xlfn.` right and `_xlpm.`
wrong is worse than getting both wrong, because it looks fixed.

*Correct OOXML for that formula* (what the serializer now produces):

```
_xlfn.LET(_xlpm.v,H10,_xlpm.p,_xlfn.XLOOKUP($B$10,tbl_pnl_summary[line_item],
          tbl_pnl_summary[polarity]),IF(_xlpm.p="contextual","n/a",IF(_xlpm.v=0,"-",
          IF((_xlpm.p="higher_favorable")=(_xlpm.v>0),"Favorable","Unfavorable"))))
```

*Shipped fix - `LET` removed rather than namespaced.* `LET` bought one thing here: naming the
polarity lookup instead of repeating it. That is not worth carrying a second namespace
obligation for a formula whose only job is to print one of four words, and repeating an
`XLOOKUP` against a fourteen-row table costs nothing. The P&L formula is now plain nested `IF`
over `XLOOKUP`:

```
=IF(XLOOKUP($B$10,tbl_pnl_summary[line_item],tbl_pnl_summary[polarity])="contextual","n/a",
 IF(H10=0,"-",
 IF((XLOOKUP($B$10,tbl_pnl_summary[line_item],tbl_pnl_summary[polarity])="higher_favorable")
    =(H10>0),"Favorable","Unfavorable")))
```

Polarity behaviour is byte-identical: verified line by line across all fourteen P&L rows -
contextual to "n/a", zero variance to "-", polarity matching the sign to "Favorable", otherwise
"Unfavorable". No value is hardcoded; the cells remain formula-driven and still read the
centralised Phase 7 polarity.

*Serializer fixed anyway.* `excel_style.qualify_formula` now namespaces declared names as well as
function names, handling nested `LET`, `LAMBDA`, parameter names that also appear inside string
literals, and idempotent re-application. The workbook ships zero `LET`, so this path is covered
by direct unit tests rather than by the workbook itself.

*Counts, from the saved package:* 668 formulas total; 481 `XLOOKUP`, all `_xlfn.`-namespaced;
**0 `LET`**; 14 formulas corrected (`P&L!J10:J23`); 1 worksheet affected (sheet5 / P&L); 0 bare
modern functions and 0 bare declared names anywhere. `fullCalcOnLoad="1"` preserved in
`xl/workbook.xml`, calculation mode automatic.

*Regression guards added.* A fifth namespacing check rejects any `LET` / `LAMBDA` parameter
lacking `_xlpm.`, anywhere in the package. Five new tests read the ZIP directly: sheet5 is
confirmed to be P&L from the workbook's own sheet order; all fourteen Fav / Unfav formulas are
confirmed present, namespaced and `LET`-free; no declared name anywhere lacks `_xlpm.`; the
guard is **mutation-tested** by reconstructing the exact broken formula and requiring the
validator to catch it; and the serializer has unit coverage for nesting, `LAMBDA` and literals.
Workbook validation goes from 99 checks to 100, tests from 26 to 31.

**Manual Microsoft Excel reopen is still required** to confirm no recovery dialog and no
`#NAME?` errors. Neither openpyxl nor pytest runs Excel's own parser, and this defect is the
reason that distinction is now stated in the documentation rather than assumed.

**Modern Excel functions were emitted without the OOXML `_xlfn.` namespace, so Microsoft 365
Excel rendered `#NAME?` in every cell using them.**

*Root cause.* Worksheet functions introduced after Excel 2007 are stored in the file format
under the `_xlfn.` future-function namespace - `_xlfn.XLOOKUP`, `_xlfn.LET` - and a few
dynamic-array functions under `_xlfn._xlws.` as well. Excel writes the prefix itself and hides
it in the formula bar, which is why a workbook saved by Excel shows `XLOOKUP(...)` on screen
while its XML holds `_xlfn.XLOOKUP(...)`. openpyxl performs no such translation: it writes the
formula string it is handed, verbatim, into the `<f>` element. The builder handed it bare
`XLOOKUP(` and `LET(`, so Excel resolved them as unrecognised defined names. Inspection of the
saved package confirmed 668 `<f>` elements containing 467 bare `XLOOKUP` and 14 bare `LET`
occurrences, and **zero** `_xlfn.` prefixes anywhere.

*Fix.* `excel_style.qualify_formula` rewrites modern function names into their required OOXML
representation at the single point every cell is written, so no formula can bypass it.
Substitution happens only outside string literals, so a lookup key or a commentary headline
containing a function name is never touched, and the transform is idempotent.
`excel_style.MODERN_FUNCTIONS` is the roster and carries the correct namespace per function
rather than blanket-prefixing - `_xlfn.SUM` is as broken as a bare `XLOOKUP`.
`excel_style.display_formula` gives the readable form back, so a structural check can be written
against `XLOOKUP("Exit ARR"` while the stored form keeps its namespace.

*Confirmed in the saved XLSX XML*, not through openpyxl: 668 formula elements, **481 namespaced
calls (467 `_xlfn.XLOOKUP`, 14 `_xlfn.LET`), zero bare occurrences**, across the eight
presentation sheets that use them. `fullCalcOnLoad="1"` is preserved in `xl/workbook.xml`, so
Excel recalculates the whole workbook on open.

*Regression guard.* `check_ooxml_function_prefixes` opens the ZIP, parses every `<f>` element in
every worksheet part, blanks string literals so a lookup key cannot be read as a function call,
and rejects four failure modes: a modern function with no namespace, a modern function with the
wrong namespace, a namespace applied to a legacy function that does not take one, and a function
call in neither the modern nor the legacy roster - an unclassified name is failed rather than
assumed safe. `XLOOKUP` and `LET` are additionally asserted by name. Workbook validation goes
from 92 checks to 99.

*The guard is mutation-tested.* Six deliberate corruptions of the saved package - every prefix
stripped (the reported defect), the prefix stripped from `XLOOKUP` alone, from `LET` alone, a
wrong namespace applied, a namespace applied to a legacy function, and an unclassified function
name introduced - and every one is caught. A check that never fails proves nothing.

No business calculation, mart, Phase 2-8 analytical result or presentation value changed. No
formula-driven cell was replaced with a hardcoded result. The workbook's 668 formulas are the
same 668 formulas, written in the representation Excel requires.

### Changed

- `src/run_sql.py` now writes `data/marts/ctl_control_results.csv` - the control roster, its
  phase label and its violation count - so the Controls tab has a committed source. The control
  results previously existed only inside `data/helio.duckdb`, which is not committed.
- `sql/manifest.yml` carries a `phase` and a `label` on each control entry. Both are presentation
  metadata: no SQL model reads them, and a control still passes if and only if its query returns
  zero rows.
- `src/build.py` regenerates the workbook from the exported marts and runs its 100 validation
  checks between the analytical layer and the test suite. A failed workbook check exits non-zero,
  exactly like a failed control. `--skip-excel` opts out.
- `requirements.txt` adds `openpyxl>=3.1`.

### Known limitations

- No cached formula results; formula values are verified against the marts in Python rather than
  read back out of the file.
- **Automated checks do not substitute for opening the file.** Neither openpyxl nor pytest runs
  Excel's own parser. A manual Microsoft Excel reopen is required to confirm no recovery dialog
  and no `#NAME?` errors.
- The workbook is a read layer: it cannot change a driver and re-forecast. Assumptions live in
  `config/assumptions.yml` under version control, not in a spreadsheet cell.
- The scenario selector drives one clearly-identified panel, by design; charts and tables
  elsewhere on the Scenarios tab always show all three scenarios.
- Segment-level Budget ARR figures are allocations - `fact_budget` carries no segment grain for
  ARR movements - and are labelled `budget_grain = 'allocated'`. Budget carries no functional
  headcount grain either, so the by-function headcount table has no Budget column rather than a
  fabricated departmental split.
- The commission asset is analytically derived, not GL-reconciled; the Accounting tab says so on
  the sheet. Accounting billings and deferred revenue are shown for actual periods only.
- Mart CSV exports are not byte-stable across rebuilds (row order within ties, and floating-point
  dust from parallel aggregation). This predates Phase 9 and affects the CSVs, not the workbook.
- PHASE1_SPEC section 10 names a five-tab workbook at `models/Helio_FPA_Operating_Model.xlsx`;
  this phase builds eleven visible tabs at `excel/Helio_SaaS_FP&A_Operating_Model.xlsx` per the
  Phase 9 brief. Recorded as a deviation from the frozen specification rather than left silent.

## [v0.7] - SaaS accounting enhancements: deferred revenue and ASC 340-40 commission capitalisation

Phase 8 of the build described in `docs/PHASE1_SPEC.md`. Adds the accounting mechanics that sit
between bookings, ARR, billings, recognised revenue, commission cash and commission expense: a
contract-level billing and deferred-revenue schedule, and an ASC 340-40 sales commission
capitalisation schedule with a full asset rollforward and a GAAP-versus-cash view.

This is an **enhancement and reconciliation layer**. It reads the frozen Phase 3-7 commercial
output and the source ledger and writes back into neither. No Phase 3-7 model, control or output
is altered, and `ctl_accounting_enhancements` fails the build if any of them moves.

### Added

**DuckDB analytical layer** - `sql/09_accounting/`
- `int_contract_billing_schedule` (contract x month) - the engine. Billing cadence read from
  `fact_contract.billing_frequency`, never inferred from segment; in-force monthly rate taken from
  `fact_subscription_monthly`; scheduled invoices at each period anchor, prorated co-terminous
  invoices for mid-term expansion (PHASE1_SPEC 2.5), and true in-arrears invoicing for
  month-to-month agreements. Billings and revenue are computed off one rate series per contract,
  so every one of the 2,213 in-scope contracts self-liquidates to a net position of exactly zero
  and the deferred-revenue rollforward closes with no plug.
- `fct_billings` (month x segment) - billings split into scheduled / prorated / arrears
  components, recognised revenue, the deferral build, TTM billings and revenue, and the TTM
  billings-to-revenue multiple. Billings growth is deliberately not headlined: 88% of in-force MRR
  bills in advance, so monthly and quarterly billings are driven by the renewal calendar.
- `fct_deferred_revenue` (month x segment) - the rollforward in both gross and net form. The
  unbilled receivable arising on arrears-billed contracts is reported as its own non-negative
  column and is never netted into deferred revenue; whether it is technically an ASC 606 contract
  asset or a receivable pending invoicing is not asserted, because the source records no invoicing
  or legal-right detail. Long-term deferred revenue is shown to be structurally zero from the
  contract population rather than assumed.
- `fct_revenue_accounting_reconciliation` (month) - contract analytical revenue vs source GL
  (accounts 4000 + 4010) vs Phase 6 management revenue, with the difference quantified and
  explained rather than closed. The contract schedule is a contract-level monthly ratable
  analytical schedule - more granular than the ledger's company-level lagged-ARR convention, but
  not a full ASC 606 subledger.
- `int_commission_earned` (path x month x deal type) - commission earned at the approved rates
  (New Logo 9%, Expansion 6%, Renewal Uplift 3%), split into the 41% expensed as incurred and the
  59% capitalised per `config: gl.commission_expensed_share`. History reads closed-won CRM
  opportunity ACV; Jul-2026 onward reads the frozen `fct_arr_forecast` movement unchanged.
- `fct_commission_amortization` (path x cohort x month) - 36-month straight-line runoff by
  capitalisation cohort, beginning in the month of capitalisation.
- `fct_commission_asset` (path x month) - the asset rollforward, the accrued commission liability
  rollforward, and the cash view (50% on booking, 50% on collection per the source collections
  curve).
- `fct_commission_accounting_reconciliation` (path x month) - ASC 340-40 vs source GL accounts
  6030 / 6040 vs the Phase 6 simplified treatment, with the accounting adjustment isolated.
- `fct_accounting_enhanced_pnl` (path x month) - the accounting-enhanced analytical S&M and
  operating-income view, explicitly labelled as an analytical view rather than a new Base
  forecast. Nothing downstream reads it.
- `fct_commission_sensitivity` (variant x path x month) - 24 / 36 / 60-month useful lives and a
  deal-type eligibility split (New Logo and Expansion capitalised, Renewal Uplift expensed under
  the stated practical-expedient interpretation), published as labelled sensitivities per
  PHASE1_SPEC 8.7. No variant is presented as the authoritative GAAP outcome.

**Controls**
- `ctl_accounting_enhancements` - the build gate, thirteen check families (A-M). Every rollforward
  is recomputed from stored component columns rather than read from a model's own residual column,
  and every opening balance is re-derived as the prior month's closing balance. Deferred revenue
  is independently re-aggregated from the contract schedule; the commission asset is independently
  rebuilt as the sum of every cohort's unamortised balance; commission earned is independently
  recomputed from `stg_fact_crm_opportunity`, bypassing every 05_gtm and 09_accounting model. The
  control was mutation-tested against 23 deliberate corruptions, all of which it catches.
  `python -m src.build` and `python -m src.run_sql` both exit non-zero on a violation.

**Reporting and documentation**
- `src/accounting_report.py` - generates `reports/accounting_enhancements_validation_report.md`:
  the executive accounting scorecard, the bookings / billings / ARR / revenue separation, the
  deferred-revenue rollforward with an independent size check, the historical revenue
  reconciliation, commission earned by deal type, the commission asset rollforward, GAAP versus
  cash commission, the Base forecast accounting effect, Bear / Base / Bull consequences, the
  accounting-enhanced P&L view, the judgement sensitivity, controls and known limitations.
- `docs/accounting_enhancements.md` - the source capability assessment, the billing convention and
  its telescoping-sum proof, the two window conventions, the deferred-revenue methodology, the
  revenue-recognition residual against the GL, the ASC 340-40 interpretation, commission
  eligibility, capitalisation policy, useful life, renewal-commission treatment, the GAAP versus
  management/cash view, and fourteen stated limitations.
- `tests/test_accounting_enhancements.py` - 35 tests. They rebuild balances from the raw source
  (`fact_contract` cadence, `fact_subscription_monthly` MRR, `fact_crm_opportunity` ACV,
  `fact_gl_actuals` accounts 6030 / 6040) rather than reading a model's own residual columns.

### Findings

- **The source ledger's commission mechanic reproduces exactly.** Immediate expense ties to
  account 6030 to the cent in all 30 actual months, and amortisation ties to account 6040 within
  $0.01 a month. The accounting adjustment to every historical month is therefore exactly zero:
  Phase 8 reproduces history rather than restating it.
- **Contract analytical revenue runs +2.64% above the source GL in FY2025.** A difference in
  recognition convention, not an accounting error in either series: the ledger recognises a 55/45
  weighted lag of prior month-end ARR, the contract schedule recognises the current month's
  in-force rate. Reported, bounded by control D, and left in place. Jan-2024 is a ledger boundary
  artifact, flagged and excluded from the tolerance test rather than hidden.
- **Deferred revenue of $10.56M at 30 Jun 2026** against a $33.02M ARR base, with an independent
  reasonableness benchmark computed from the billing mix alone predicting $10.53M.
- **The 36-month amortisation period follows from the rate card, not from preference.** Renewal
  commission (3% on uplift only) is not commensurate with the initial commission (9% of ACV), so
  under ASC 340-40-35-1 the expected benefit period extends beyond the 12-month initial term.
- **The accounting adjustment is immaterial** - $22.8k in H2 2026 and $85.8k in FY2027, roughly
  0.1-0.2% of revenue. Reported as a finding rather than dressed up as a swing factor.
- **The frozen 41/59 policy is more conservative than a deal-type eligibility split**, which would
  capitalise more because Renewal Uplift is only ~1.3% of earned commission.

### Known limitations

The revenue schedule is a contract-level monthly ratable analytical schedule, not a full ASC 606
subledger: no daily service-period proration for mid-month commencement or termination, invoice
months but no invoice dates, and contract grain rather than performance-obligation grain. The
unbilled receivable's balance-sheet classification - contract asset versus receivable pending
invoicing - is not asserted, because the source records no invoicing or legal-right detail. The
commission asset is analytically derived, not GL-reconciled - the source carries no balance sheet.
It opens at zero on 1 Jan 2024, matching the ledger's own cohort window and understating the true
balance by the pre-2024 tail. Deferred revenue is subscription only; the source records services
revenue but no services billing event. 42 of 2,255 contracts (1.9%), all with service starting on
or after 2 Jun 2026, are outside the schedule. No commission impairment line, no accelerators, and
no standalone-selling-price allocation. All fourteen are stated in
`docs/accounting_enhancements.md` section 10 and in the validation report.

## [v0.6] — Board Budget → Q2 Base reforecast bridges and deterministic commentary

Phase 7 of the build described in `docs/PHASE1_SPEC.md`. Turns the approved Phase 3–6
analytical layer plus `fact_budget` into a full set of Budget-to-Base variance bridges (ARR,
Revenue, Gross Profit, OpEx, Operating Income, Headcount) and a deterministic, SQL-templated
management commentary engine — no LLM anywhere in the pipeline. The independent Base reforecast
(Phase 6) remains the forecast explained; `fact_forecast` appears only as a small secondary
comparison. No Phase 3–6 model, control or output is altered.

### Added

**DuckDB analytical layer**
- `sql/07_bridge/` — `int_metric_polarity`, `int_materiality_thresholds`, `int_commentary_params`
  (centralised favorable/unfavorable, materiality and wording-rule config, read from
  `config/commentary_rules.yml`); `int_budget_reforecast_comparison` (the central Budget-vs-Base
  metric × segment comparison table every bridge reads); `fct_arr_budget_bridge` (Dec-2026 Exit
  ARR, company and by segment); `fct_new_logo_diagnosis` (capacity-vs-pipeline diagnostic,
  separate from the dollar bridge because Phase 6's `New Logo ARR = LEAST(capacity, pipeline)`
  cannot be split additively); `fct_revenue_budget_bridge` (Subscription / Services / Total,
  decomposed into a recognition-mechanic effect and an ARR / New-Logo effect using the exact
  formulas `fct_pnl_reforecast` already uses); `fct_gross_profit_bridge` (with gross-margin bps);
  `fct_opex_budget_bridge` (payroll / commissions / non-payroll, by category); `int_commentary_
  candidates` (driver-level ranking and share-of-variance, the data behind "primarily" and
  "offset"); `fct_headcount_budget_bridge`; `fct_operating_income_bridge`; `fct_management_
  variance` (the normalized, ranked variance mart); `fct_commentary_output` (the deterministic
  commentary itself).
- `ctl_bridge_commentary` — the build gate. Fourteen checks: every bridge reconciles Budget +
  components = Base exactly (ARR, Revenue, Gross Profit, OpEx, Operating Income), segment ARR
  bridges sum to the company bridge, the headcount comparison is internally consistent, no plug
  or balancing line exists anywhere, every commentary driver amount traces to a real stored value
  in its declared source model, materiality is enforced, priority values are valid, commentary
  IDs are unique, favorable/unfavorable polarity is independently re-derivable, and top-driver
  ranking is independently re-derivable. `python -m src.build` and `python -m src.run_sql` both
  exit non-zero on a violation.
- `src/bridge_report.py` — generates `reports/executive_variance_report.md`: a data-selected
  Executive Summary, the FY2026 scorecard, every bridge in full, the New Logo operating
  diagnosis, headcount, Board-policy runway context, the hiring decision (affordability and
  attractiveness kept separate), the full deterministic commentary set, controls and known
  limitations.
- `config/commentary_rules.yml` + `src/commentary_rules.py` — materiality thresholds, metric
  polarity, and commentary-wording/priority parameters, loaded into DuckDB the same way
  `config/assumptions.yml: forecast` already is. Reporting rules, never business results.
- `data/marts/` — eleven more curated CSV exports.

**Methodology**
- Budget's ARR movement components (New Logo / Expansion / Reactivation / Contraction / Churn)
  carry no segment grain in the source data (`fact_budget`'s memo accounts post company-level
  only). Segment bridges therefore ALLOCATE Budget's company figures — New Logo by the FY2025
  New Logo ARR mix (`int_gtm_new_logo_mix`, reusing Phase 5's own precedent for exactly this
  problem), the other four movements by each segment's share of actual 31-Dec-2025 ARR — while
  Base's segment figures stay real and segment-native throughout. Beginning ARR needs no
  allocation at all: it is real, shared history, identical on both sides.
- Revenue bridge effects are calculated by running the identical recognition mechanic
  (`fct_pnl_reforecast`'s ARR-lag weights and New-Logo-attach ratio) over Budget's own ARR/New
  Logo path, never a fabricated price-volume split.
- Headcount is bridged only at the grain Budget supports (`fact_budget` account 9200 is a single
  company-level statistical figure); Base's own by-function detail is reported separately rather
  than reverse-engineering a Budget functional plan that doesn't exist in the source.
- Commentary "primarily" and "offset" language is gated by calculated driver-share-of-variance
  thresholds, never asserted; priority is assigned from centralised dollar/percentage thresholds,
  never because a number is merely negative; materiality suppresses immaterial rows except two
  mandatory governance items (Board-policy runway, the hiring decision).

**Tests**
- `tests/test_bridge_commentary.py` — 25 pytest tests covering every bridge's reconciliation
  independently re-derived in pandas, segment bridges summing to the company total, opening ARR
  parity, no plug lines, gross-margin bps arithmetic, favorable/unfavorable polarity (including
  headcount's deliberate non-polarity), materiality suppression, top-driver ranking, the
  "primarily" and "offset" gating rules, commentary traceability to real stored values, runway
  and hiring commentary reading the Board-policy view rather than the operating-cash proxy, and a
  cross-tie confirming Phase 6's own `fct_arr_forecast` is unchanged by this phase.

**Documentation**
- `README.md` updated: Phase 7 marked complete, "What Phase 7 produces" section, repository
  structure extended.

### Notes

- FY2026 Board Budget → Base: Exit ARR $37.59M → $34.82M (-$2.77M, primarily New Logo ARR
  -$2.79M, partly offset by Expansion +$1.54M); Revenue $33.63M → $32.79M (-$0.84M); Gross Profit
  $24.91M → $25.69M (+$0.78M, +429 bps margin, driven by lower Subscription COGS payroll cost
  relative to Budget); Total OpEx $30.54M → $31.41M (+$0.87M, primarily payroll); Operating Loss
  $5.63M → $5.71M (-$0.09M, immaterial — correctly suppressed from standalone commentary);
  Headcount 214 → 217.7 FTE.
- Pipeline, not capacity, binds New Logo ARR in 15 of 18 H2 2026 segment-months — the primary,
  data-derived reason New Logo ARR misses Budget.
- Base policy runway 25.6 months (1.6 months of headroom); Bear breaches the 24-month floor at
  23.5 months; Full Capacity-Close hiring is affordable (24.7 months) but adds only $467 of
  incremental Dec-2026 ARR because pipeline remains the binding constraint; Targeted hiring
  computes to zero incremental hires.
- `ctl_bridge_commentary`, alongside `ctl_arr_reconciliation`, `ctl_retention_bounds`, `ctl_gtm_
  controls` and `ctl_forecast_controls`, all pass with zero violations; the full pytest suite
  (181 tests across all phases) is green.

## [v0.4] — GTM capacity, pipeline, CRM-to-ARR reconciliation, unit economics

Phase 5 of the build described in `docs/PHASE1_SPEC.md`. Loads six more raw tables into the
DuckDB layer for the first time — `dim_sales_rep`, `dim_employee`, `fact_crm_opportunity`,
`fact_marketing_spend`, `fact_gl_actuals` and the FY2026 board budget — and turns them into
sales rep capacity with ramp, pipeline coverage, a customer-matched CRM-to-ARR bridge, unit
economics with a documented cost-allocation methodology, and two separately-defined
sales-efficiency metrics. No driver-based forecasting, scenarios, runway modelling, Excel or
Power BI — those are later phases. `fct_arr_movement` and the retention/renewal layer are not
altered.

### Added

**DuckDB analytical layer**
- `sql/01_staging/` — six new typed pass-throughs (`stg_dim_sales_rep`, `stg_dim_employee`,
  `stg_fact_crm_opportunity`, `stg_fact_marketing_spend`, `stg_fact_gl_actuals`,
  `stg_fact_budget`).
- `sql/02_core/dim_sales_rep.sql`, `dim_employee.sql` — conformed dimensions.
- `sql/05_gtm/` — `int_rep_month` (rep × actual-month ramp spine), `int_crm_opportunity_normalized`,
  `int_crm_closed_won`, `int_gtm_cost_allocation` (new-logo acquisition cost, by cost centre ×
  month × segment), `fct_sales_capacity`, `fct_rep_attainment`, `fct_pipeline_snapshot`,
  `fct_crm_bookings`, `fct_crm_arr_reconciliation`, `fct_unit_economics`, `fct_sales_efficiency`.
- `ctl_gtm_controls` — the build gate. Capacity and ramp bounds, an attainment-denominator
  guard, pipeline non-negativity, win-rate bounds, CRM-to-ARR bridge arithmetic, the FY2025 New
  Logo residual tolerance (fulfilling PHASE1_SPEC's `ctl_crm_to_arr`), cost-allocation
  reconciliation, a CAC divide-by-zero guard and a sales-efficiency denominator guard.
  `python -m src.build` and `python -m src.run_sql` both exit non-zero on a violation.
- `src/gtm_report.py` — generates `reports/gtm_validation_report.md`: executive GTM scorecard,
  capacity by segment, rep attainment distribution, pipeline by quarter/segment/deal type, sales
  cycle and win rate, the CRM-to-ARR bridge in full, unit economics with an allocation
  sensitivity, sales efficiency, the capacity gap, controls and known limitations.
- `src/load_database.py` now loads eleven of the thirteen raw tables (`fact_requisition` and
  `fact_forecast` remain out of scope until Phase 6).
- `data/marts/` — nine more curated CSV exports.

**Methodology**
- Blended, account-based quota-crediting convention: attainment credits New Logo, Expansion and
  Renewal Uplift ACV against a ramped monthly quota, since `dim_sales_rep` carries one quota per
  rep and pays commission on all three deal types — there is no separate new-logo-only rep
  population in the source data.
- CRM-to-ARR New Logo bridge is customer-matched: every New-Logo opportunity is linked to that
  customer's next ARR landing event (New Logo or Reactivation) on or after the CRM close month.
  A small self-serve population — ARR-side New Logo events with no matching CRM opportunity at
  all — is computed independently, not solved as a plug; with it, the FY2025 residual ties to
  $0.00 (0.00% of $5.29M FY2025 New Logo ARR, against a 0.5% tolerance).
- Cost allocation deviates from a literal reading of PHASE1_SPEC 8.5 (which assumes separate
  new-logo and expansion AE populations that do not exist in this dataset): AE, SDR, Sales Ops,
  Solutions Engineering and Leadership cost is split across segments by active AE headcount
  (`dim_sales_rep`, the literal "AE headcount split"), and the acquisition percentage for the
  blended pools uses the realised FY2025 New Logo share of closed-won ACV.

**Tests**
- `tests/test_gtm_capacity.py` — 26 pytest tests covering the ramp schedule re-derived
  independently, terminated reps carrying no post-termination capacity, capacity = quota × ramp
  × expected attainment, historical win rate excluding open opportunities and re-derived from
  raw CRM data, weighted pipeline = ACV × stage probability, Enterprise sales cycle exceeding
  SMB, closed-won bookings excluding open/lost records, non-provisioned wins never landing as
  ARR, the CRM-to-ARR bridge reconciling mathematically and within tolerance, the lagged CAC
  convention, gross-margin-adjusted payback, cost-allocation reconciliation to the GL pool, the
  Magic Number and Net ARR Sales Efficiency using different formulas, and no duplicate rep-month
  records.

**Documentation**
- `docs/gtm_finance.md` — capacity and ramp methodology, the blended quota-crediting convention,
  pipeline and win-rate definitions, the CRM-to-ARR bridge (New Logo customer-matched, Expansion
  aggregate), the cost-allocation deviation and methodology, CAC/payback, sales efficiency, rep
  performance, the capacity-gap input, and known limitations.
- `README.md` updated: Phase 5 marked complete, "What Phase 5 produces" section, repository
  structure and documentation index extended.

### Notes

- 16 active quota-carrying reps at 30 June 2026 (SMB 5, Mid-Market 7, Enterprise 4); FY2025 CAC
  $16,294 (SMB) / $71,385 (Mid-Market) / $310,652 (Enterprise), blended $36,337, blended payback
  25.0 months, gross-margin adjusted at a company-level 76%-scale margin (segment margin is not
  supportable from the source).
- FY2025 Net ARR Sales Efficiency averaged 0.41 and the classic Magic Number 0.43, both within
  the same order of magnitude as the PHASE1_SPEC illustrative anchors (0.42 / 0.34) despite being
  computed independently from generated data, not typed to match.
- `ctl_gtm_controls`, `ctl_arr_reconciliation` and `ctl_retention_bounds` all pass with zero
  violations; the full pytest suite (106 tests across all phases) is green.

## [v0.2] — ARR engine, customer-grain classification, waterfall

Phase 3 of the build described in `docs/PHASE1_SPEC.md`. Turns `fact_subscription_monthly`
into a customer-level ARR movement engine and reconciles it. No retention, NRR, GRR, GTM
capacity, forecast, scenarios, Excel or Power BI — those are later phases.

### Added

**DuckDB analytical layer**
- `sql/manifest.yml` and `sql/01_staging/`, `02_core/`, `03_arr/`, `08_controls/` — one SELECT
  statement per model, executed in manifest order by `src/run_sql.py`. No dbt, no
  orchestration framework, per `docs/decisions.md`.
- `src/load_database.py` loads the four raw tables the ARR engine needs (`dim_customer`,
  `dim_product`, `dim_date`, `fact_subscription_monthly`) into a DuckDB database.
- `int_arr_customer_month` and `int_arr_customer_product_month` — dense customer-month and
  customer-product-month spines built from the sparse source table before any `LAG()` runs,
  so a churn followed by a reactivation can never be read as a single expansion.
- `fct_arr_movement` — the customer-grain ARR movement engine, classifying every
  customer-month against the six binding rules (PHASE1_SPEC 8.2).
- `fct_arr_product_movement` — the same six rules at customer × product grain, explicitly
  separate and non-tying on categories, for product-mix analysis only.
- `fct_arr_waterfall`, `fct_arr_snapshot`, `fct_arr_concentration`.
- `ctl_arr_reconciliation` — the build gate. Checks `Beginning + New Logo + Expansion +
  Reactivation − Contraction − Churn = Ending` at company-month, segment-month and full-period
  grain, plus the customer/product ARR tie, tolerance $1.00. `python -m src.build` and
  `python -m src.run_sql` both exit non-zero on a violation.
- `src/arr_report.py` — generates `reports/arr_validation_report.md`: monthly ARR trend, the
  FY2025 waterfall against the PHASE1_SPEC anchors, movement totals and movement by segment,
  reconciliation results, largest churn/expansion months, and the anchor variance discussion.
- `data/marts/` — curated CSV exports of the five 03_arr models, committed per the
  "readable without running" convention.

**Tests**
- `tests/test_arr_engine.py` — 14 pytest tests covering classification validity, each of the
  six binding rules re-derived independently of the classifying SQL, no duplicate
  customer-months, no negative ARR, company and segment waterfall reconciliation, and that a
  same-month product substitution nets correctly at customer grain instead of inflating
  expansion and contraction.

**Documentation**
- `docs/arr_engine.md` — movement grain, the dense-spine rationale, classification
  methodology, the customer-vs-product distinction, reconciliation logic, the FY2025 result
  against the Phase 1 anchors with cause analysis, and known limitations.
- `README.md` updated: Phase 3 marked complete, "What Phase 3 produces" section, repository
  structure and documentation index extended.

### Notes

- FY2025 waterfall: beginning $24.52M (target $24.2M, +1.3%), new logo +$5.28M (+5.6%),
  expansion +$4.26M (-3.3%), reactivation +$0.08M (-62.1%), contraction -$1.62M (-80.1%), churn
  -$2.36M (+15.7%), ending $30.15M (+0.2%). ARR level ties tightly at both ends; the
  movement-category composition diverges further because the Phase 2 calibration loop was
  solved against total ARR, logo counts and retention, never against the dollar split across
  movement categories. Full analysis in `docs/arr_engine.md`.
- The expansion sub-type split (seat/module vs. renewal price uplift) is deferred: it needs
  `fact_contract.uplift_pct_at_renewal`, which is outside this phase's minimal four-table load
  and isn't required by any of the six binding classification rules.
- `data/helio.duckdb` is the analytical-layer database file, gitignored and rebuilt on demand.

## [v0.1] — Synthetic data foundation with renewal mechanics

Phase 2 of the build described in `docs/PHASE1_SPEC.md`. Produces the raw source dataset that
every later phase reads, plus the machinery that proves it is coherent. No analytical layer,
no metrics, no forecast.

### Added

**Configuration**
- `config/assumptions.yml` holding every calibrated financial driver — anchors, segment
  definitions, contract mechanics, retention hazards, expansion behaviour, CRM targets, quotas
  and ramp, headcount and attrition, ledger cost drivers, and the two planning versions.
  Nothing a reviewer would want to challenge is buried in Python.
- `config/chart_of_accounts.yml` — 26 natural accounts crossed with 21 operating cost centres,
  each rolling up to one of the eight reporting functions and one of the seven approved P&L
  categories. Ten statistical accounts for the planning tables.
- `config/name_lists.yml` — curated components producing contractor-style customer names, with
  a banned-token list enforced by the validation suite.

**Generation**
- Deterministic seeded generator producing 13 source tables in `data/raw/`. Random streams are
  keyed per entity, so a customer's journey does not shift when other cohorts change size.
- Contract engine with monthly, annual and multi-year terms; churn and contraction confined to
  the anniversary or end of term; bounded early termination; mid-term co-termed expansion; and
  a 3–5% renewal price uplift expressed as a narrowing of the discount to list.
- Seats modelled as a penetration of the customer's own workforce, with a per-customer ceiling
  that expansion cannot exceed.
- Journey archetypes driving coherent multi-year customer histories, with churn hazard varying
  by segment, size, tenure and calendar year.
- Renewal seasonality emerging from acquisition seasonality rather than being imposed, giving
  Q1 and Q4 renewal concentration and lumpy monthly churn.
- CRM opportunities carrying the five reconciling differences the Phase 5 walk needs:
  signing-to-provisioning lag, TCV against ACV, wins that never provision, post-close
  amendments, and renewal uplift booked as an opportunity.
- Sales reps, employees and requisitions, with reps appearing in both `dim_sales_rep` and
  `dim_employee` so headcount and rep counts cannot drift apart, and requisition backfills tied
  to the terminations that caused them.
- General ledger built from drivers — payroll person by person, hosting per seat, commissions
  from closed-won ACV — never by spreading annual totals across months.
- FY2026 board budget and FY2026 Q2 reforecast, each built by applying movement components to
  the opening ARR the data actually carried rather than by typing an exit position.

**Calibration**
- Deterministic feedback loop solving nine parameter groups against the approved ARR, logo,
  new-logo ACV, retention and P&L anchors by staged bisection. No anchor value is written into
  the output.

**Validation and tests**
- `src/validate_sources.py` — 105 checks run against the committed CSVs rather than the
  generator in memory.
- `src/report.py` — generates `reports/source_validation_report.md` on every build.
- `tests/test_source_data.py` — 41 pytest tests covering reproducibility, the ARR and MRR
  identity, churn timing, segmentation, referential integrity and the anchors.
- `python -m src.build` runs the whole sequence and exits non-zero on a critical failure.

**Documentation**
- `README.md`, `docs/data_dictionary.md`, `docs/generation_methodology.md`.

### Notes

- `docs/PHASE1_SPEC.md` is frozen and unchanged.
- Nine documented departures from the specification are recorded in
  `docs/generation_methodology.md` section 8, covering the source-table count, the scope of
  `dim_customer`, the opening balance month, the `recent_new_logo` archetype, segment logo
  tolerance, the 198 FTE against 206 headcount reconciliation, row-count estimates, implied R&D
  compensation, and the treatment of the Enterprise NRR figure.
