# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v0.9.8] - Visual QA against the rendered report

With the project opening, refreshing and rendering in Desktop, the five pages were reviewed as a
reader sees them, against screenshots. The palette, header system, conclusion-led titles and page
flow held up. Density did not.

**No layout was redesigned, no page architecture changed and no calculation moved.** Every change
is density, formatting or a totals setting. All six upstream controls pass and the
expected-results pack still holds its 157 rows unchanged.

### Root causes

**Power BI writes its own subtitle** from the field names - "Deferred Revenue, Unbilled Receivable
and Capitali...", "Policy Runway Months and Board Floor...". It appeared on every visual, repeated
the title, truncated, and took a line of plot area. Never authored by us; now off in the theme.

**The deferred-revenue panel rendered as a placeholder icon.** Not a binding or schema fault: at
152px, after a two-line title and that auto-subtitle, no plot area was left, and Desktop
substitutes an icon rather than draw nothing.

**Totals summed alternatives.** The hiring-case table showed "Total 4.0 / $147,322" across three
mutually exclusive cases; the runway table totalled months across paths.

### Fixed

- **Columns cut in nine tables** to clear the horizontal scrollbars: KPI band 10 -> 8, both
  Budget-vs-Base scorecards 6 -> 5, GTM KPIs 8 -> 6, pipeline band 10 -> 4, ARR movement by
  segment 7 -> 5, retention by segment 5 -> 4, headcount 5 -> 4, hiring case 7 -> 5, runway detail
  6 -> 5, scenario summary 6 -> 5. Every table now has at least 81px per column.
- **The auto-generated subtitle is off**, fixing every truncated subtitle in the pack at once.
- **The accounting panel** has 186px and renders.
- **Totals off** on the hiring-case table and both runway tables.
- **The Board floor is a dashed amber reference line at 24 months**, labelled, on both runway
  charts, instead of a second series that read as another bar.
- **Zero labels suppressed** where zero is not the message: an empty third format section renders
  zero as blank, so the bridge's "$0.00M" step and the ATR chart's rows of "$0.0M" are gone.
- **The ARR movement axis** moved Thousands -> Millions: "$2,000K" beside a "$40.0M" secondary
  axis read as two different reports.
- **Sales efficiency and the Magic Number** read "0.43x" rather than "0.43".
- **Short bridge labels.** A `Bridge Step` column shortens "Opening ARR variance (31-Dec-2025
  actual, identical both sides)" to "Opening ARR" for the category axis. Presentation only - the
  full wording stays on the stored `Bridge Line`, now hidden, and no amount is touched.
- **The assumptions matrix renders flat** - stepped layout and the [+] toggles off.
- **Geometry rebalanced** on pages 1, 4 and 5 for the taller KPI band and the two charts that had
  been squeezed into 170px.

### Added

- `MODEL_ONLY_MEASURES` - the nineteen measures the trimmed tables no longer display. They are
  kept rather than deleted: each is documented in `measures.md`, several are exercised by the
  SQL-to-DAX pack, and a reader opening the model should find the obvious companion metric. Two
  checks keep the list honest - nothing on a page may claim the exemption, and anything new that
  stops being read still fails.
- `check_visual_density` - 16 checks, taking the validator from 503 to **519**: columns against
  width, charts against a minimum height, no overlap, nothing off canvas, the auto-subtitle off,
  no over-long title, no total on a table of alternatives, the Board floor as a reference line,
  and the exemption list honest.
- Tests 121 to **141**, including three mutation tests: an overcrowded table, a chart too small to
  render, and a restored scenario total.

### Caught by Microsoft's validator during the pass

- `y1AxisReferenceLine.dataLabelText` is an enum (Value / Name / ValueAndName), not free text. The
  wording belongs in `displayName`; the label now reads "Board floor 24".
- Two panel labels were dropped to 30px, below the 34px floor for a 10pt font. Restored.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING.** This pass is a response to screenshots and
  needs another look on screen.
- Executive tables still read full dollars rather than millions (v0.9.7): a table column's display
  unit needs a per-column selector whose shape is not documented in the published schema package.

## [v0.9.7] - Display units: format strings state the unit, visuals state the scale

Desktop rendered the report and the numbers were unreadable. Axes read `$0MM`, table cells read
`$4,781,152.1,,M` and `$853,381K`, chart labels read `$2.1,,MM`. Every underlying value was
correct; two scaling mechanisms were fighting each other.

**This is a presentation fix only.** No DAX arithmetic, no business logic, no mart, no SQL model,
no page layout and no visual position changed. All six upstream controls pass and the
expected-results pack still holds its 157 rows unchanged.

### Root cause

**A scaling comma is only honoured at the end of a format section.** Followed by a suffix -
`#,##0.0,,"M"` - the tabular engine behind Power BI stops reading it as a scaler and prints it.
Excel is lenient here; Power BI is not. Every format *without* a scaler had always rendered
correctly (`23.5 mo`, `74.1%`, `534`, `0.43`), which is what identified the pattern.

On charts a second fault compounded it: a visual's display units default to **Auto**, so Power BI
scaled by a million and appended `M`, and the format string then scaled again - `$34.8M` became
`$0MM`. Setting `labelDisplayUnits: 0` on data labels in v0.9.5 had not helped, because `0` means
Auto, not "use the measure's format" as it had been read.

### Fixed

**Format strings no longer scale or carry a currency suffix.** `FMT_USD_M`, `FMT_USD_M2` and
`FMT_USD_K` are gone; currency is `\$#,##0;(\$#,##0);\$0` and signed currency
`+\$#,##0;(\$#,##0);\$0`. Percentages, months, ratios, basis points and counts are unchanged -
they never scaled and always worked. 60 measures now share the plain currency format.

**Every chart states its display unit explicitly** - `valueAxis.labelDisplayUnits` and
`labelPrecision`, plus `secLabelDisplayUnits` for a combo chart's second axis. 14 charts, nothing
left on Auto:

| Visual | Axis | Renders |
|---|---|---|
| Exit ARR bridge, scenario ARR, forward ATR, H2 capacity, revenue, accounting panel | Millions, 1 dp | `$37.6M`, `$3.7M`, `$15.2M` |
| Operating income bridge | Millions, 1 dp axis / 2 dp labels | `$0.09M` on a $5.7M walk |
| ARR movement (primary), GTM constraint | Thousands, 0 dp | `$346K`, `$519K` |
| ARR movement / revenue margin (secondary) | Millions / None | `$34.8M`, `78.4%` |
| Retention trend, efficiency pair | None | `101.8%`, `0.43` |
| Policy runway, affordability | None, 1 dp | `24.0 mo` |

**Data labels state the same unit as the axis they sit against**, so a label and its axis cannot
disagree. The `DATA_LABELS` constant from v0.9.5, which set Auto, is replaced by `data_labels()`.

**The scorecard's dynamic format no longer scales either**, so `$6,000,000.0,,M` becomes
`$6,000,000`.

### Known cost

A table column has no display-unit setting in a generated PBIR file: the per-column selector shape
is not documented in the published schema package, and this project no longer guesses at PBIR
shapes. **Table cells therefore show full dollars** - `$37,589,316`, `($2,793,686)` - which is
unambiguous but less compact than `$37.6M`. Charts, where scale matters most for reading a trend,
carry proper units. Getting `$37.6M` into the executive tables means setting per-column display
units in Desktop and saving back; that is the one open presentation item.

### Added

- `value_axis()` and `data_labels()` in `src/powerbi_report.py`, with the Power BI display-unit
  enum named (`AUTO_UNITS`, `NO_UNITS`, `THOUSANDS`, `MILLIONS`) so `0` can never again be read as
  "use the measure's format".
- Three checks, taking the validator from 501 to **503**: no format string scales; every chart
  states its axis display unit and none is on Auto; every data label states the same unit as its
  axis. The scorecard scaling check from v0.9.6 is inverted - it asserted the suffix *was* a
  scaled quoted literal, which is exactly what does not work.

### Changed

- `THOUSANDS_SCALE_MEASURES` and `MILLIONS_LEGIBILITY_FLOOR`, added in v0.9.5, are removed. They
  encoded the idea that a measure's *format* carries its scale; scale is a property of the visual.
- The v0.9.5 and v0.9.6 tests built on that idea are replaced. Scorecard row expectations now read
  full dollars.

### Repaired

While removing the superseded tests, a regex-driven deletion cut roughly half of
`tests/test_powerbi_report.py`, including the scaffold, namespace and report-pages blocks from
v0.9.1 to v0.9.4. The file was rebuilt from the saved blocks and every recovered test re-run; the
suite is back to 121 tests in that file and 392 overall, all passing.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING.** This pass needs a confirming look at the axes,
  labels and tables on screen.
- Executive tables read full dollars rather than millions - see Known cost above.

## [v0.9.6] - Management Variance scorecard formatting

Three defects in the mixed-metric Budget-vs-Base scorecard, seen in Power BI Desktop.

**This is a formatting fix only.** No mart, no SQL model, no page layout and no visual position
changed, and no Budget, Base or Variance quantity changed. All six upstream controls pass and the
expected-results pack still holds its 157 rows unchanged.

### Root causes

**1. The millions suffix was an escape, not a quoted literal.** The currency branch read
`"$#,##0.0,,\M;($#,##0.0,,\M)"`. Written that way the trailing `,,` stops being read as a
thousands scaler and prints as a literal comma, so six million dollars rendered
`$6,000,000.0,M` and the Exit ARR budget rendered `$37,589,315.8,M`. Inside a DAX string a quote
is doubled, so the branch is now `""M""`, emitting the same `"M"` the static `FMT_USD_M` has always
used successfully.

**2. Gross margin was shown in basis points as a level.** The mart stores gross margin in bps -
7,406.9 budget, 7,835.9 base, 429.0 variance - because bps is the unit its *variance* is quoted
in. A level, though, reads as a percentage. No format string can bridge that: a scaling comma
divides by 1,000 and `%` multiplies by 100, and there is no divide-by-100 token.

**3. A Total row summed mixed units.** The scorecard's rows are different metrics, so the total
added dollars to basis points to headcount.

### Fixed

**Currency** - `$6.0M`, `$37.6M`, `($5.6M)` for levels; `($2.79M)`, `+$0.90M` for variances.
Variances carry **two** decimals because at one the $88K operating-income variance and the $50K
G&A variance both collapse to `$0.1M`. Levels keep one decimal, where the smallest figure is
$5.9M. Negatives take accounting parentheses.

**Gross margin** - the two level measures express the basis-point rows as a ratio and format them
`0.0%`, so Budget reads `74.1%` and Base `78.4%`. The variance is untouched and stays `+429 bps`.
This is a change of unit, not of quantity: 7,406.9 bps and 0.74069 are the same margin, and the
mart is not modified. The conversion is driven off the existing `Unit` metadata, never off value
magnitude.

**Headcount** - `214.0`, `217.7`, `+3.7`. No currency, no percent, no bps.

**Variance %** - one decimal throughout: `-46.6%`, `-7.4%`, `+6.2%`.

Both measures remain numeric. `FORMAT()` is not used anywhere, so sorting, aggregation and chart
behaviour are intact, and a test asserts it stays absent.

Every row now reads:

| Metric | Budget | Base | Variance |
|---|---|---|---|
| Ending Headcount | 214.0 | 217.7 | +3.7 |
| Gross Margin | 74.1% | 78.4% | +429 bps |
| New Logo ARR | $6.0M | $3.2M | ($2.79M) |
| Exit ARR | $37.6M | $34.8M | ($2.77M) |
| Sales & Marketing | $14.5M | $15.4M | +$0.90M |
| Total OpEx | $30.5M | $31.4M | +$0.87M |
| Revenue | $33.6M | $32.8M | ($0.84M) |
| Gross Profit | $24.9M | $25.7M | +$0.78M |
| Operating Income / (Loss) | ($5.6M) | ($5.7M) | ($0.09M) |
| Research & Development | $10.1M | $10.1M | ($0.08M) |
| General & Administrative | $5.9M | $6.0M | +$0.05M |

### The total row

Removed from four tables whose rows are incommensurable metrics: both Budget-vs-Base scorecards
(pages 1 and 4), the executive KPI band (a single row, where a total is pure duplication) and the
scenario assumptions matrix (drivers in rates, dollars, multiples and months).

Totals stay **on** everywhere else, deliberately. Power BI recomputes a measure in the total row's
filter context rather than summing what is on screen, so a total over segments gives a correctly
blended NRR and a total over P&L line items gives the company figure. Turning totals off
everywhere would have destroyed that.

A flat table and a matrix use different objects for this - `total.totals` and
`subTotals.rowSubtotals` - and they are not interchangeable.

### Section 9 - the same measures elsewhere

The generic scorecard measures are read by exactly two visuals, `p1v3_budget_vs_base` on page 1
and `p4v2_scorecard` on page 4. The fix is central, in the measures themselves, so both are
corrected by the same change; a test asserts the consumer set and that both have totals disabled,
so a third consumer cannot be added without being covered.

### Added

- `MIXED_METRIC_TABLES` in `src/powerbi_model.py` - the four tables whose rows do not aggregate,
  with the reason recorded against each.
- Seven checks added to `check_measure_presentation`, taking the validator from 494 to **501**:
  the scorecard's dollars scale by millions (the escaped-suffix defect), and each mixed-metric
  table shows no total row.
- Tests 126 to **147**, including a row-by-row assertion of all eleven scorecard rows against the
  mart's own values, and two new mutation tests: escaping the millions suffix, and restoring the
  total row.
- A small format renderer in the test suite pins what each format string means - the millions
  scaler, the percent scaling, the sign sections, the accounting parentheses - so a format edit
  that changes what a reader sees fails a test rather than reaching Desktop.

### Changed

- `test_scorecard_levels_are_unsigned_and_the_variance_is_signed`, added in v0.9.5, asserted the
  basis-point level format was `#,##0 bps`. That convention is superseded: a level is a
  percentage. The test now asserts the corrected convention rather than the old one.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING.** The project opens, refreshes and renders; this
  pass needs a confirming look at the scorecard on screen.
- No static check proves how Power BI renders a format string. The renderer in the test suite is
  a faithful model of the format rules these formats use, not a Power BI emulator.

## [v0.9.5] - Number, label and axis formatting

The project opens, refreshes and renders in Power BI Desktop, and the layout reads as designed.
What remained was presentation: some labels showed `$0.0M` for figures that were not zero, some
axes had lost their resolution, and the scorecard's dynamic format put a `+` on a level.

**This is a formatting pass only.** No DAX, no arithmetic, no business logic, no mart, no SQL
model, no page layout and no visual position changed. All six upstream controls pass, the
expected-results pack still holds its 157 rows unchanged, and every number in the report is the
number it was before - it is now legible.

### Root cause

Display scale had been chosen per measure by convention rather than from the values each measure
actually carries. A millions format with one decimal renders anything under $500K as `$0.xM` and
anything under $50K as `$0.0M`, and several dollar *flows* live well below that floor while the
*balances* beside them are in tens of millions.

Reactivation ARR has a monthly median of **$8.5K** and was formatted at millions, so it displayed
`$0.0M`. It was not the only one.

### Fixed - 17 measures reformatted

Scale is now taken from the magnitude each measure carries at the grain its visual reads it, never
from its name. The magnitudes come from the committed marts:

| Measure | Magnitude | Was | Now |
|---|---|---|---|
| Reactivation ARR | $8.5K monthly | `$0.0M` | `$9K` |
| Contraction ARR | $96.5K | `$0.1M` | `$97K` |
| Churn ARR | $188.7K | `$0.2M` | `$189K` |
| New Logo ARR | $345.7K | `$0.3M` | `$346K` |
| Expansion ARR | $472.3K | `$0.5M` | `$472K` |
| Services Revenue | $56.7K monthly | `$0.1M` | `$57K` |
| New Logo Capacity | $181.7K per segment-month | `$0.2M` | `$182K` |
| Pipeline Supported ARR | $123.4K | `$0.1M` | `$123K` |
| Constrained New Logo ARR | $108.7K | `$0.1M` | `$109K` |
| New Logo Productive Capacity (Actual) | $128.3K by segment | `$0.1M` | `$128K` |
| Policy Avg Monthly Burn | $771K-$926K | `$850,000` | `$850K` |
| Incremental ARR / Operating Income / Cash Impact (4 hiring measures) | $18.6K-$637.1K | `$147,322` | `$147K` |
| Operating Income Bridge Amount | $35.8K-$5.7M | `$0.0M` | `$0.04M` (two decimals) |

Two distinct failures, either sufficient on its own: the figure **rounds away** (smallest value
under $500K), or it **never reaches a million** (policy burn spans $771K-$926K, which millions
squeezes into `$0.8M`-`$0.9M`, losing the difference between the paths).

Millions was not removed, only removed from the measures it was wrong for. Ending ARR ($30.2M),
Revenue ($2.5M monthly), Deferred Revenue ($15.2M), ATR by quarter ($3.7M), the H2 GTM totals
($5.3M-$9.3M), the Exit ARR bridge and every scorecard headline keep it.

The operating-income bridge is the one place a decimal was added rather than a unit changed: its
steps run $35.8K to $5.7M, too wide for thousands, and at one decimal the smallest step read
`$0.0M`.

`FMT_USD_K` also now renders an uppercase `K` (`$842K`, not `$842k`).

### Fixed - the dynamic scorecard format

- The **level** measures (Budget, Base Reforecast) were printing a leading `+` on the basis-point
  row, so a 7,836 bps gross margin read `+7,836 bps`. A level carries no sign convention; only a
  variance does. Budget and Base are now unsigned in every unit, and Variance vs Budget stays
  signed in every unit.
- A `pct` branch was added so a future percentage metric cannot fall through to the count
  fallback.
- A dollar sign may now appear only on the `usd` branch, checked line by line - a leaked `$` would
  print `$7,836` on the gross-margin row and `$218` on headcount.

Both dynamic measures still use `formatStringDefinition` only; the v0.9.2 conflict is not
reintroduced, and a check asserts it.

### Fixed - data labels

The theme turned data labels off everywhere, which is right for a 24-to-48 month line chart but
wrong for a handful of discrete columns where the reader wants the figure rather than a position
against an axis.

Labels are now on for six visuals and no others: the two Budget-to-Base waterfalls, H2 capacity
versus pipeline, forward ATR by quarter, and the two runway charts. No line chart labels its
points. Each label is set to `labelDisplayUnits: 0` and `labelPrecision: -1` - "use the measure's
own format string" - so a label and a table cell can never disagree about the same figure.

**No axis or label carries a hardcoded display unit or precision anywhere in the report.** The
model format string remains the single source of truth for every measure, and a check enforces it.

### Added

**Presentation constants** in `src/powerbi_model.py`
- `KNOWN_FORMATS` - the fifteen formats the report may present, so an ad-hoc format cannot creep
  in.
- `THOUSANDS_SCALE_MEASURES` - the sixteen dollar measures whose values are thousands-scale, with
  the magnitudes that justified each one recorded alongside.
- `MILLIONS_LEGIBILITY_FLOOR` ($500,000) and `DATA_LABELLED_VISUALS`.

**A presentation check family** - `check_measure_presentation`, 10 checks, taking the validator
from 484 to 494
- Every visible measure uses a declared format.
- Every thousands-scale dollar measure is formatted in thousands - the zero-label regression.
- No format mixes a percent sign with a currency scale.
- No chart axis mixes unit kinds; dollars and percentages belong on separate axes.
- Data labels are on the intended visuals only, and no line chart labels every point.
- No data label overrides the measure's own display unit or precision.
- The scorecard's dynamic format covers every unit its mart carries, with dollars confined to the
  dollar branch.

**Regression and mutation tests** - 102 tests to 126
- The magnitudes behind every scale decision are **re-derived from the marts at test time**, so
  the declared list cannot drift away from the data that justified it.
- The converse guard: measures kept at millions are asserted to be millions-scale.
- Percentage measures return ratios and never multiply by 100 themselves - a measure that did
  would render NRR as 10,180%. Multiples (`0.43`, `2.87x`) are checked separately from
  percentages, because the expected pack labels both "ratio".
- Months and multiples carry no currency symbol.
- Levels are unsigned and the variance is signed, per unit.
- Three mutation tests: Reactivation ARR put back to millions, a percentage added to a dollar
  axis, and a data label forced to millions with zero decimals.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING.** The project opens, refreshes and renders; this
  pass needs a confirming look at the numbers on screen.
- No static check can prove how Power BI renders a label. These checks catch semantic-unit
  mismatches - a dollar flow at a scale that rounds it away, a percentage without a percent sign,
  a month count with a currency symbol - not the rendering itself.

## [v0.9.4] - Report-definition version fix after the fourth Desktop acceptance failure

Power BI Desktop opened the project and **refreshed the semantic model successfully** - 27 tables,
all loading. It then displayed **no report pages at all**, replaced the report with a blank
single-page report of its own, and saved over it. Five pages and 45 visuals were discarded without
one error message.

**This is a report-packaging fix only.** No DAX, no measure, no business logic, no expected result,
no mart, no SQL model and no part of the Phase 9 Excel workbook was touched. All six upstream
controls pass and the expected-results pack still holds its 157 rows unchanged.

### Root cause

`definition.pbir` carries a `version` that tells Desktop **which report-definition format to
read**. It said `"1.0"`; Desktop writes `"4.0"`. At `"1.0"` Desktop does not look in
`definition/pages/` at all - so the five pages were not rejected, they were never read. Finding a
report definition it considered empty, Desktop created `Page 1` and wrote the project back.

**Nothing could have caught it.** `definitionProperties` types `version` as a free-form string, so
the published schema accepts any value; Microsoft's own PBIR validator passed the project; and
every check here confirmed the five page folders, their `page.json` files and all 45 `visual.json`
files existed exactly where they should - because they did.

The defect was also self-inflicted and recent: the generator originally emitted `"4.0"`, and it
was changed to `"1.0"` during the v0.9.1 work, reasoning from a schema that types the field as a
string and therefore constrains nothing, rather than from evidence.

### The Desktop scaffold, at last

Desktop overwriting the report left behind a complete **Desktop-authored PBIP** - the ground truth
v0.9.1 to v0.9.3 worked without, having only a `.pbix` to go on. Comparing it against the
generator settled several open questions at once:

| File | Desktop | Ours | Outcome |
|---|---|---|---|
| `definition.pbir` `version` | `4.0` | `1.0` | **the defect** |
| `definition.pbir` `$schema` | absent | present | kept - `definitionProperties` marks it required |
| `definition/version.json` | `2.0.0` | `2.0.0` | confirmed |
| `page.json` schema and shape | `page/2.1.0` | `page/2.1.0` | confirmed |
| `.platform`, `.pbism`, `.pbip` | - | - | byte-identical, `logicalId` included |
| `report.json` `themeCollection` | `baseTheme` | `customTheme` only | **fixed** |
| `database.tmdl` `compatibilityLevel` | `1606` | `1601` | adopted Desktop's |
| All 27 table TMDL files | Desktop's own | ours | **accepted verbatim** |

The last row is worth stating plainly: Desktop rewrote every table file and changed only its own
normalisations - it dropped `crossFilteringBehavior: oneDirection` (a default), unquoted
identifiers it considers bare-safe, and added a trailing newline. **No measure, column, format
string, relationship or partition was altered.** The TMDL this project generates is the TMDL
Desktop writes, which v0.9.2 could not establish at the time.

### Fixed

- **`definition.pbir` `version` is now `4.0`**, read off Desktop's own file. The constant carries
  a comment saying what it decides and that it must not be "simplified".
- **The report declares a base theme.** Desktop packages one with every report, and the schema
  describes a custom theme as one "applied on top of the base theme", with undefined properties
  falling back to it. Ours declared a custom theme and no base at all. The report now declares
  both, in Desktop's shape: `Fluent2-CY26SU08` as a `SharedResources` package with
  `HelioExecutive.json` layered over it. The base theme file in `src/powerbi_assets/` is
  Desktop's own, copied verbatim. This did not cause the missing pages, but it was a real defect
  in the same file found by the same comparison.
- `report.json` also adopts Desktop's `objects.section` vertical alignment and the three further
  `settings` keys it writes.
- `compatibilityLevel` raised 1601 -> 1606, Desktop's own value, so a Desktop round-trip leaves
  `database.tmdl` unchanged.

### Added

**A Desktop contract** - `DESKTOP_PBIR_CONTRACT` in `src/build_powerbi.py`
- The values Desktop reads, recorded as Desktop itself writes them. Checked against Desktop's
  behaviour rather than against what a schema permits, because the schema permitted the defect.

**A report-pages check family** - `check_report_pages`, 40 checks, taking the validator from 444
to 484
- Every contract value matches Desktop's own, `definition.pbir` `version` first among them.
- `pageOrder`, the page folders and each `page.json` `name` form one bijection, in declared order;
  `activePageName` names a real page; no page folder is orphaned out of `pageOrder`.
- Every page has a non-empty `displayName`, is not `HiddenInViewMode`, and is not typed `Tooltip`
  or `Drillthrough` - three further ways to produce the same "no pages" symptom.
- Every `visual.json` sits in its own folder under the page's `visuals/`, names itself after that
  folder, parses, and carries `name` and `position`; no stray files or undeclared folders.
- The base theme is declared and packaged.
- No Power BI Desktop local state is committed.

**Regression and mutation tests** - 86 tests to 102
- Five mutation tests: `version` set back to `"1.0"`, a page dropped from `pageOrder`, a page
  marked hidden, a `visual.json` renamed, and `.pbi/localSettings.json` planted. The first
  reproduces the exact failure - on a project Microsoft's validator still passes.
- A test asserting the committed `RepoRoot` parameter is still empty and carries no machine path.

**`.gitignore` for what Desktop writes into an opened project**
- `.pbi/localSettings.json` (a machine-bound security-binding signature), `.pbi/cache.abf` (a
  local cache of the loaded model data), `.pbi/editorSettings.json`, and `diagramLayout.json`.
  Desktop had also stamped `RepoRoot` in `expressions.tmdl` with this clone's absolute path -
  exactly what the committed-empty-parameter rule exists to prevent. Regenerating restores it, and
  two checks fail the build if any of it reaches the repository.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING**, now after four failed attempts. The semantic
  model opens and refreshes; the report pages have never been seen to render.
- **`visual.json`'s schema version is still inferred.** The Desktop-authored scaffold is a blank
  report, so it contains no visuals and still cannot settle the visual container version. A
  Desktop `.pbip` with at least one visual on a page would.
- **Desktop normalises the TMDL it saves**, so a Desktop session leaves a diff against the
  generated project even when nothing meaningful changed. Regenerate with
  `python -m src.build_powerbi` before committing; Desktop's save is not the source of truth.

## [v0.9.3] - Semantic-model namespace fix after the third Desktop acceptance failure

The v0.9.2 format fixes worked: Power BI Desktop began creating model objects. It then refused
one:

```text
The 'Ending ARR' measure cannot be created because a column with the same name already exists.
PFE_XL_MEASURE_COLUMN_ALREADY_EXIST
```

**This is a semantic-model naming fix only.** No mart, no CSV, no SQL model, no Power Query step
and no part of the Phase 9 Excel workbook was renamed or altered. All six upstream controls still
pass, the expected-results pack still holds its 157 rows unchanged, and no reported number moved.

### Root cause

Columns, measures and hierarchies in one table share a single **case-insensitive** namespace. A
measure cannot take a name a column in the same table already holds. `ARR Forecast` carried both
a stored column `Ending ARR` and a measure `Ending ARR` reading it.

Desktop stops at the first invalid object, so it named one of **23 collisions across 8 tables**:

| Table | Colliding names | Count |
|---|---|---:|
| ARR Forecast | Beginning ARR, New Logo ARR, Expansion ARR, Reactivation ARR, Contraction ARR, Churn ARR, Ending ARR | 7 |
| Headcount | Beginning Headcount, Hires, Departures, Ending Headcount | 4 |
| Runway Policy | Policy Avg Monthly Burn, Policy Runway Months, Board Floor Months | 3 |
| Retention | Cohort Customers, Cohort Beginning ARR | 2 |
| GTM Constraint | New Logo Capacity, Constrained New Logo ARR | 2 |
| Sales Capacity | Expected Attainment, Actual Bookings | 2 |
| Scenario Monthly | Scenario Operating Income, Scenario Ending Cash | 2 |
| New Logo Diagnosis | Budget New Logo ARR | 1 |

All 23 were column-to-measure. The model has no hierarchies, so column-to-hierarchy collisions
were structurally impossible; no table declared a measure name twice; and no measure name was
reused across the model.

### Fixed - the ` Source` convention

**The measure keeps the business name. The stored column takes a ` Source` suffix and stays
hidden.**

```text
measure      Ending ARR                    <- what the field list shows
column       Ending ARR Source             <- hidden, exists only to be summed
sourceColumn Ending ARR                    <- unchanged: the Power Query output name
mart column  fct_arr_forecast.ending_arr   <- unchanged
```

TMDL allows the semantic-model column name to differ from `sourceColumn`, so the rename is
confined to the semantic model. `Ending ARR`, `New Logo ARR`, `Revenue`, `Gross Profit`,
`Operating Income`, `Ending Headcount`, `Policy Runway Months` and the rest keep the names a
reader looks for. Renaming the measures instead, or moving them to a disconnected Measures table,
would have cost exactly the clarity the report exists to provide - a Measures table was considered
and rejected as an architecture change to a naming defect.

**Blast radius: 23 column declarations and 31 DAX column references.** All 23 colliding columns
were already hidden, none was used as a sort-by column, a relationship key, or a field on any
visual, and no measure in another table referenced one - so nothing outside those files needed to
move. Three ratio-discipline checks in `src/validate_powerbi.py` that assert stored-column names
by string were updated to match.

### One latent defect the fix revealed

`unused_measures()` - the check enforcing PHASE1_SPEC's restraint rule, that every measure is read
by a visual or by a measure that is - had been passing on a false positive. It matches
`[Measure Name]` in DAX text, and a fully-qualified **column** reference such as
`'Sales Capacity'[Actual Bookings]` matched too. Once the columns were renamed, two measures stood
exposed as genuinely unread: `Sales Capacity[Actual Bookings]` and
`Scenario Monthly[Scenario Ending Cash]`.

Both were resolved by having the measures that duplicated their aggregation call them instead:

- `Actual Attainment` summed `'Sales Capacity'[Actual Bookings Source]`, which is literally the
  definition of `[Actual Bookings]`. A textually identical substitution.
- `Scenario Dec-27 Cash` summed `'Scenario Monthly'[Scenario Ending Cash Source]` under a
  Dec-2027 filter; `[Scenario Ending Cash]` is that sum under `LASTNONBLANK`. The mart holds
  exactly one row per scenario at 2027-12-31 and it is each scenario's last month, so the two
  return the same value - verified against the mart, not reasoned about.

No arithmetic changed. An aggregation is now defined once rather than twice, which is the state
the collision had been hiding.

### Added

**The invariant, enforced at two levels**
- `Table.__post_init__` in `src/powerbi_model.py` refuses a colliding declaration
  case-insensitively, so the specification fails to import rather than emitting a model Desktop
  will reject.
- `check_table_namespace` in `src/validate_powerbi.py` rebuilds the namespace from the **emitted
  TMDL** - columns, measures and hierarchies - independently of the specification.

**A table-namespace check family** - 6 checks, taking the validator from 438 to 444
- No column, measure or hierarchy shares a name within a table, case-insensitively.
- No table declares the same measure name twice.
- Every measure name is unique across the whole model.
- The namespace scan actually read the model (a scan that finds nothing because it parsed nothing
  is not a check).
- Every ` Source` column is hidden from report view.
- The ` Source` suffix appears only where a measure claims the name, so the convention cannot
  spread into columns that never needed it.

**Regression and mutation tests** - 75 tests to 86
- The emitted TMDL carries no same-table collision; measure names are unique model-wide; the
  recruiter-facing measure names survived the rename; ` Source` columns are hidden and
  non-gratuitous; `sourceColumn` still names the Power Query output and the marts still carry
  their physical column names.
- Every DAX column reference resolves to a real column, so a rename cannot silently leave a
  measure pointing at a name that no longer exists.
- Four mutation tests: a colliding declaration, a collision differing only in case, a ` Source`
  column renamed back in the emitted TMDL, and a duplicated measure name.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING**, now after three failed attempts. Each got
  further than the last: PBIR loading, then measure metadata, then object creation. Desktop may
  still object later in model creation, at first refresh, or when rendering a visual.
- The limitations recorded in v0.9.1 and v0.9.2 are unchanged: `visual.json`'s schema version is
  still inferred rather than read off a Desktop-authored file, and no offline TMDL validator is
  available on this machine.

## [v0.9.2] - TMDL measure-format fix after the second Desktop acceptance failure

The section 12 scaffold fixes worked: Power BI Desktop read the PBIR report and moved on to
building the semantic model. It then rejected the model:

```text
The Measure 'Management Variance'['Budget'] has both FormatString property and
FormatStringDefinition property defined which is not supported scenario.
PFE_TM_MEASURE_FORMAT_STRING_DEFINITION_CONFLICT
```

**This is a TMDL serialization fix only.** No DAX arithmetic, no business logic, no expected
result, no mart, no SQL model and no part of the Phase 9 Excel workbook was touched. All six
upstream controls still pass and the expected-results pack still ties to the frozen marts. Every
measure returns exactly the number it returned before; what changed is how its display format is
declared.

### Root cause

A measure may declare a static `formatString` **or** a dynamic `formatStringDefinition`, never
both - and Power BI rejects the whole model rather than the offending measure. Four measures
declared both. Desktop stops at the first, so its message named only one of them.

Format-mechanism inventory across all 108 measures:

| | Before | After |
|---|---:|---:|
| Static `formatString` only | 103 | 103 |
| Dynamic `formatStringDefinition` only | 0 | 4 |
| **Both (invalid)** | **4** | **0** |
| Neither (text measure) | 1 | 1 |

### Fixed

The four conflicting measures now carry the **dynamic** property only. Dynamic is the correct
mechanism for each - the static property was the one that had to go, because these measures are
deliberately generic over a mixed-unit metric set:

- `Management Variance[Budget]`, `[Base Reforecast]`, `[Variance vs Budget]` - one measure reads
  whatever metric is in context, and the set mixes nine USD rows, one basis-point row (the
  gross-margin walk) and one FTE row (headcount). The static format they carried printed a dollar
  sign in millions on the basis-point and headcount rows.
- `Forecast Drivers[Driver Value]` - one stored value across rates, dollars per month,
  multipliers and months. No single static format serves four units.

Everything with one stable unit keeps a static format string. No dynamic format was introduced
where a static one suffices, and no measure was stripped of formatting to dodge the conflict.

Two presentation details that dropping the static property would otherwise have cost:
- `Variance vs Budget` is a variance, and its static format carried a leading `+` the shared
  `SWITCH` did not. It now has its own signed variant, so a positive variance still reads `+$1.2M`.
- `Forecast Drivers` carries a `months` unit the `SWITCH` never named, so those rows fell to the
  numeric fallback and rendered unlabelled. A `months` branch was added.

The measures stay numeric. `FORMAT()` was deliberately not used inside any expression to sidestep
the model metadata - that returns text and breaks sorting, aggregation and chart behaviour.

- `src/powerbi_docs.py` - a measure with no static format printed `Format | None` into
  `powerbi/measures.md`, a Python `None` leaking into the generated documentation. It now reports
  whichever mechanism the measure actually uses.

### Added

**The invariant, enforced at three levels**
- `Measure.__post_init__` in `src/powerbi_model.py` raises on the combination, so a conflicting
  measure cannot be declared at all - the specification fails to import rather than emitting TMDL
  Desktop will reject.
- `measure_tmdl` in `src/build_powerbi.py` refuses to serialise the pair.
- `check_measure_formats` in `src/validate_powerbi.py` parses the **written TMDL** back and
  checks it independently of both, because the emitted file is what Desktop opens.

**A measure-format check family** - 5 checks, taking the validator from 433 to 438
- No measure carries both properties, read out of the emitted TMDL.
- Every measure the specification declares was found in the emitted TMDL.
- The dynamic-format measures are exactly the ones the specification names.
- Dynamic format strings are confined to the mixed-unit measures.
- The only unformatted measure is the one that returns text.

**Regression and mutation tests** - 66 tests to 75
- The `SWITCH` in each dynamic format covers every unit value actually present in its mart, so a
  unit cannot render unlabelled through the fallback.
- `Variance vs Budget` keeps a signed format distinct from the level measures.
- Three mutation tests: declaring both properties is refused by the specification; the serialiser
  refuses to emit the pair even when the guard is bypassed; and a `formatString` planted back
  into a dynamic measure's TMDL fails validation.

### Swept, no further conflicts found

Since Desktop had advanced into TOM model creation, the rest of the model metadata was checked
rather than assumed clean: duplicate property lines within any member block, `sortByColumn`
targets, `formatString` on non-numeric columns, aggregating `summarizeBy` on string columns,
hidden key columns, table `dataCategory`, partitions per table, relationship names and lineage
tags (302, all unique). `compatibilityLevel` is 1601, well above the level dynamic format strings
require. Nothing further was found - which is a sweep, not a proof.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING**, now after two failed attempts. Each got
  further than the last; Desktop may still object at a later stage of model creation or at first
  refresh.
- **No offline TMDL validator was available.** The Desktop reference from v0.9.1 is a `.pbix`,
  whose model is a binary Analysis Services backup rather than TMDL, and being a blank report it
  contains no measures at all - so it could not settle measure syntax either way. Neither the
  .NET SDK nor `pbi-tools` is installed, and Microsoft's PBIR CLI validates the report, not the
  semantic model. What the failure does establish is that Desktop parsed `formatStringDefinition`
  correctly and objected only to the pairing, so the property syntax is confirmed by Desktop
  itself.

## [v0.9.1] - PBIR packaging fix after the first Desktop acceptance failure

Power BI Desktop (August 2026, 2.157.879.0) refused to open
`powerbi/Helio_Executive_Report.pbip`:

```text
Cannot find file 'version.json'
Error Reading StorageSection: ReportDocument
```

**This is a serialization and packaging fix only.** No measure, no DAX, no expected result, no
mart, no SQL model and no part of the Phase 9 Excel workbook was touched. All six upstream
controls still pass and the expected-results pack still ties to the frozen marts.

The report definition was never written to `Report/definition/version.json`, and Desktop reads
that file before anything else - so the load aborted at the first missing file and reported
nothing about the rest. Validating the project against Microsoft's PBIR validator found **65
errors and 6 warnings**; the missing file was one of them.

### Root cause

`src/validate_powerbi.py` tested the project thoroughly against **its own specification** and not
at all against **Power BI's requirements**. There was no check that the Desktop scaffold was
complete, so a required file the generator never wrote was invisible to it: 409 of 409 checks
passed on a project Desktop could not read.

### Fixed

**The missing scaffold file**
- `Report/definition/version.json` is now generated on every build, with the `$schema` and the
  `version` value `2.0.0` taken verbatim from a project written by the installed Desktop build.

**PBIR schema versions**, migrated to the versions the August 2026 Desktop scaffold emits. Not a
version-string replacement - the shapes changed, and the files were rewritten accordingly.

| File | Was | Now |
|---|---|---|
| `definition/version.json` | absent | `versionMetadata/1.0.0`, `version: "2.0.0"` |
| `definition/report.json` | `report/1.0.0` | `report/3.3.0` |
| `definition/pages/pages.json` | `pagesMetadata/1.0.0` | `pagesMetadata/1.1.0` |
| `definition/pages/*/page.json` | `page/1.0.0` | `page/2.1.0` |
| `definition.pbir` | no `$schema`, `version: "4.0"` | `definitionProperties/1.0.0`, `version: "1.0"` |
| `visuals/*/visual.json` | `visualContainer/1.0.0` | `visualContainer/2.9.0` |

**Formatting objects in the wrong place** - 54 of the 65 errors
- `title`, `background` and `border` were written into `visual.objects`. They are **container**
  objects and now go to `visual.visualContainerObjects`. `general` deliberately stays where it
  is: the textbox's `general.paragraphs` and the slicer's `general.orientation` are visual-level.

**Theme registration** - the theme would have silently failed to apply
- `customTheme.name` now carries the required `.json` extension and matches both the
  `RegisteredResources` item and the `name` inside the theme file itself. All three must agree.
- `customTheme.type` is now `"RegisteredResources"`; the legacy `reportThemeType` property, which
  `report/3.3.0` forbids, is gone.
- `customTheme.reportVersionAtImport` is now written; `report/3.3.0` requires it.
- `layoutOptimization` removed - `report/3.3.0` sets `additionalProperties: false` and no longer
  carries it.
- The slicer theme block used `items.fontSize`; that object sizes text with `textSize`.

**Enum and uniqueness defects**
- Slicer `general.orientation` was `2`; the enum admits `0` and `1` only. Now `1` (horizontal),
  which is what the 456x44 slicer geometry was always drawn for.
- Filter names are now qualified with the visual that carries them. A filter name must be unique
  across the whole report, and the page declarations share filter constants.
- The two page-5 panel labels were 24px tall, below the 34px floor for a 10pt font, and would
  have rendered with a scrollbar. Now 34px, moved to y=292 so they still sit exactly between the
  chart above and the visuals below.

### Added

**A declared scaffold contract** - `REPORT_SCAFFOLD` and `MODEL_SCAFFOLD` in
`src/build_powerbi.py`
- Every file Desktop needs, and the `$schema` each must carry, declared once. The generator writes
  from it and `src/validate_powerbi.py` asserts against it, so the two cannot drift and a file
  that stops being written fails the build instead of reaching Desktop.

**A scaffold check family** - `check_scaffold`, 30 checks, taking the validator from 409 to 433
- Every scaffold file exists, parses and carries the pinned `$schema`.
- `version.json` carries the approved version value and no properties beyond the schema's two.
- Every page.json and visual.json carries its pinned schema.
- Every PBIR definition file declares a `$schema` at all.
- No container formatting object sits in `visual.objects`.
- Every filter name is unique across the report.
- Four further theme checks: type, `reportVersionAtImport`, absence of `reportThemeType`, and the
  theme file's own `name` matching the registration.

**Regression and mutation tests** - `tests/test_powerbi_report.py`, 37 tests to 66
- Presence, parse and pinned-schema tests for every scaffold file, parametrised off the contract.
- Six mutation tests that prove the new guards actually fail: deleting `version.json`, downgrading
  its version value, reverting `report.json` to the 1.0.0 schema, stripping the `$schema` from
  `definition.pbir`, misfiling a container formatting object, and colliding two filter names.
  A guard that has never been made to fail is not a guard.

**Microsoft's PBIR validator as an independent check**
- `npm install -g @microsoft/powerbi-report-authoring-cli@latest` then
  `powerbi-report-author validate powerbi/Helio_Executive_Report.pbip`, which now reports
  **0 errors, 0 warnings**. It validates against the live published schemas rather than against
  this repository's understanding of them, and `powerbi-report-author doctor` confirms schema
  reachability so the check is not silently skipped.

### Changed

- `docs/powerbi_executive_report.md` - new section 12 recording the failure in full: the Desktop
  error, the root cause, the full diagnostic table, where each corrected value came from, the
  before/after schema table, and why the automated checks missed it. The project tree now shows
  `version.json`, the check count is 433, and the status line at the top states plainly that the
  first acceptance attempt failed and that Desktop acceptance remains PENDING.
- `README.md` and the phase table updated to the same effect.

### Still outstanding

- **Power BI Desktop acceptance remains PENDING.** The project has not yet been successfully
  opened in Desktop. Passing Microsoft's validator is a much stronger signal than passing our own
  checks, but it is not Desktop, and the whole point of this entry is that the difference matters.
- **`visual.json`'s schema version is inferred, not confirmed.** A blank Desktop report contains
  no visuals, so the scaffold gave no sample. `visualContainer/2.9.0` is the highest published
  version in the family, is consistent with the `2.0.0` report definition version, and validates -
  but it is the one part of the contract not read off a Desktop-authored file. A `.pbip` saved
  from Desktop with at least one visual on the page would settle it, and would also supply a
  Desktop-authored `definition.pbir`, `.pbism` and `.platform` to check the project wrapper
  against; the reference available here was a `.pbix`, which contains none of those.

## [v0.9] - Power BI executive report

Phase 10 of the build described in `docs/PHASE1_SPEC.md`. Adds
`powerbi/Helio_Executive_Report.pbip` - the executive reporting interface over the frozen Phase
3-8 analytical stack, generated reproducibly from the committed marts.

Committed as a **Power BI Project (PBIP), not a `.pbix`**: a TMDL semantic model and a PBIR report
definition, both plain text. A `.pbix` in a public repository is an opaque binary whose diff reads
"binary files differ"; a PBIP puts every measure, every Power Query step, every relationship and
every visual into the pull request. That is the whole reason for the format choice, and it is why
the project is generated rather than hand-authored - the generator is the specification, and the
build fails if the committed files have drifted from what it emits.

The report is a **read and present layer**. Every business calculation stays in `sql/`; DAX reads
stored values and forms presentation ratios over them. No Phase 2-8 model, control, mart or output
is altered, and generating the project reads nothing from `data/marts` at all - the marts are the
report's runtime source, not a build input.

No `.pbix` binary. No embedded data. No machine-specific path. No cloud dependency, no gateway and
no workspace. No benchmark value anywhere - see Known limitations.

### Added

**The project** - `powerbi/Helio_Executive_Report.pbip` (629 KB across 31 TMDL files and 45 visual
definitions)
- **Five pages**, six analytical visuals each per the PHASE1_SPEC section 12 ceiling, with slicers
  and text blocks treated as chrome rather than analysis. Every visual title is a conclusion or a
  question, never a noun.
- **Executive Q2 Reforecast** - the scorecard band, the Exit ARR bridge ($2.8M below Budget, New
  Logo ARR most of the gap), Budget versus Base ranked by variance, Bear / Base / Bull ARR to
  Dec-2027, Board-policy runway against the 24-month floor, and the Phase 7 rules engine's
  Critical and High commentary items.
- **ARR, Retention & Renewals** - ARR movement with Ending ARR on a combo axis where the forecast
  line starts exactly where the actual line stops, the NRR / GRR / logo-retention trend, FY2026
  movement by segment, TTM retention at 30 June 2026 by segment, acquisition-cohort retention by
  cohort age, and forward ATR by quarter.
- **GTM Capacity & Pipeline** - H2 2026 capacity against pipeline-supported bookings against the
  constrained figure that is the lesser of the two, the same three series monthly, capacity and
  conversion by segment, FY2025 unit economics, and Net ARR Sales Efficiency and the Magic Number
  plotted as a labelled pair, never combined into one number.
- **Financial Performance & Headcount** - the management P&L pivoted on fiscal year, the FY2026
  Budget-versus-Base scorecard carrying the Phase 7 centralised favourability rather than
  re-deriving it, the operating-income bridge, revenue with gross margin on a second axis, the
  deferred-revenue and capitalised-commission panel, and the headcount rollforward.
- **Plan & Scenarios** - split into two labelled halves because they are two different questions:
  (A) affordability, policy runway against the 24-month floor and the burn behind each path;
  (B) attractiveness, what the incremental hiring case buys on the FY2027 horizon.

**The semantic model** - 27 tables, 108 measures, 27 relationships
- Three dimensions built in Power Query from literal lists: `Date` (daily and contiguous
  2023-12-01 to 2027-12-31, marked as the model's date table, carrying the `Period Type` column
  that flips Actual to Forecast at the 2026-06-30 cutover and drives every actual/forecast split
  in the report), `Segment` and `Scenario`, both with explicit sort columns.
- 24 fact tables, one per committed mart, each reading its CSV through a single `RepoRoot`
  parameter. Power Query filters `segment <> 'Total'` and `path = 'Base'` on the way in, so the
  marts' own pre-aggregated rows cannot double count.
- Every relationship single-direction and many-to-one onto a dimension. **No bi-directional
  filter and no many-to-many relationship anywhere in the model.**
- **Eight tables deliberately left disconnected**, each with its reason recorded in
  `DISCONNECTED_NOTES` and asserted by a test so a later edit cannot quietly connect one.
  `Runway Policy` is the clearest: its five paths span three operating scenarios *and* two hiring
  cases, which a three-member Scenario dimension cannot represent, so a join would strand the
  hiring rows on a blank member. `Management Variance`, `Commentary`, `Operating Income Bridge`,
  `Cohort ARR`, `Unit Economics`, `CRM Opportunities` and `New Logo Diagnosis` follow for their
  own stated grain reasons.
- 108 measures (104 visible, 4 hidden supporting) across eleven display folders - ten business
  folders numbered in reading order plus `99 Supporting` - each carrying its number format in the
  model so a figure reads identically wherever it appears.

**Measure discipline**, enforced by the validator rather than by convention
- **SQL owns the business logic.** Movement classification, the TTM cohort and its per-customer
  GRR cap, available-to-renew, ramp and capacity, `LEAST(capacity, pipeline)`, every driver, the
  bottom-up P&L, the Board-policy runway, the computed hire counts, every bridge, materiality,
  polarity and the commentary text are produced upstream. A measure either reads a stored value or
  forms a presentation ratio over stored values.
- **Every ratio is a ratio of aggregates, never an average of ratios.** `AVERAGE` appears nowhere
  in the model and the build fails if it ever does. Averaging the three segment NRRs at Jun-2026
  gives 98.1%; the correct ARR-weighted ratio of aggregates gives 101.8%. One of those would have
  been wrong on a board page.
- **A measure with no defined value returns BLANK.** `Magic Number` and `Net ARR Sales Efficiency`
  across more than one quarter, TTM retention across more than one month, and
  `Policy Runway Months` across more than one path all return blank rather than a
  plausible-looking number. `Ending ARR` is semi-additive: a year returns its final month, never a
  sum of twelve.

**Generated documentation and the SQL-to-DAX pack**
- `powerbi/measures.md` (2,400 lines) - every measure with its DAX, format, display folder, source
  mart and fields, the SQL that produces the same number, its filter-context behaviour, and which
  visuals read it. Generated by `python -m src.powerbi_docs`; the test suite regenerates it on
  every run and fails if the committed copy has drifted, so **documented DAX and shipped DAX
  cannot diverge**.
- `powerbi/validation/dax_validation_queries.dax` - the queries a reviewer runs in Power BI
  Desktop or DAX Studio, with the run instructions and the tolerances stated in the file.
- `powerbi/validation/expected_measure_results.csv` - **157 expected values generated from the
  committed marts by Python** (`python -m src.powerbi_expected`), each with its filter context,
  unit, source mart and the SQL behind it. Tolerances: ratios to 4 decimal places, dollars to $1,
  months to 0.01.

**Validation** - `src/validate_powerbi.py`, 409 static checks, plus 37 tests in
`tests/test_powerbi_report.py`
- Files and JSON parse (42 + 2); the report references the semantic model beside it by relative
  path (3).
- Model (40): every declared table, column, data type and format present in TMDL; the Date table
  marked as one, contiguous across the calendar, with Period Type flipping at the right cutover.
- Relationships (35): all 27 present, every one single-direction and many-to-one onto a dimension,
  and the eight disconnected tables still disconnected.
- Measures (155): all 108 present with their declared format and home table, plus the
  ratio-discipline checks on the named measures and model-wide.
- Sources (9): every mart a Power Query references is committed under `data/marts/`.
- No machine paths (3): no drive letter, no home directory, no absolute path, nothing reaching the
  internet, anywhere in the project.
- Pages and visual fields (78 + 3): exactly the five pages PHASE1_SPEC section 12 names, every
  measure and column a visual references exists, and no visual uses an implicit measure.
- Theme (5) and generated artifacts (6): the theme is registered, referenced and packaged with the
  declared palette; `measures.md` and the expected-results CSV regenerate identically.
- Project regenerates (27): every committed table TMDL is byte-identical to what the specification
  emits. Lineage tags are `uuid5` over a fixed namespace rather than random, so a no-op rebuild
  leaves an empty diff and drift detection means something.

**Build integration** - `src/build.py`
- The Power BI project, its measure library and its expected-results pack are regenerated after
  the Excel workbook and put through the 409 static checks in the same run; a failure names what
  broke and exits non-zero. `--skip-powerbi` leaves the project alone.
- The build prints `Power BI Desktop acceptance is a separate, manual step` rather than implying
  the checks are complete.

**Documentation** - `docs/powerbi_executive_report.md`
- Why a PBIP project rather than a `.pbix`, the five pages, the semantic model and every
  disconnected table's reason, measure design, opening the project and the `RepoRoot` parameter,
  the formatting standard, the traceability chain from `visual.json` back to the controls, what
  the 409 checks prove and what they cannot, the manual Power BI Desktop acceptance route, the
  deviations from the frozen spec and the known limitations. Includes a **"How to review this
  project in 5 minutes"** route that needs no Power BI install.

### Known limitations

- **Power BI Desktop acceptance is outstanding.** Python does not open Power BI Desktop. The 409
  checks prove the static assets are internally consistent and agree with the marts; they cannot
  prove that Desktop's parser accepts a hand-authored PBIR file, that a visual renders, that DAX
  executes, that a slicer cross-filters, or that a label is legible at 1280x720. The validator
  never reports that Power BI passed - it reports
  `POWER BI STATIC VALIDATION OK - Power BI Desktop acceptance still required`, and DAX execution
  validation is stated as PENDING in the queries file itself. `docs/powerbi_executive_report.md`
  section 11 is the acceptance route. **This is the largest open item in the phase.**
- **No benchmark appears anywhere in the report.** PHASE1_SPEC section 12 lists benchmarks for
  several metrics; section 9 of the same spec permits one only where the source's own formula has
  been read and confirmed to match Helio's definition. This repository carries no benchmarks
  document and no confirmed source formula, and the spec is explicit that an omitted row with a
  stated reason beats a fabricated comparison.
- **The Budget-versus-Base scorecards carry no prior-year column.** The spec asks for actual /
  budget / reforecast / prior year on pages 1 and 4. The page 4 P&L does show prior year, pivoted
  on fiscal year; the scorecards do not, because `fct_management_variance` carries only the Budget
  and Base amounts the Phase 7 layer computes and controls. Assembling a prior-year column from a
  different mart at a different grain would put an uncontrolled number on a board page.
- **Rep attainment distribution, top churn and expansion accounts, and open reqs / slippage are
  not shown**, and customer concentration appears as a measure rather than a visual. Six
  analytical visuals per page is a hard ceiling in the same spec section; these lost to the
  visuals that answer the eight management questions directly. The underlying marts exist.
- The report is a read layer: it cannot change a driver and re-forecast. Assumptions live in
  `config/assumptions.yml` under version control, not in a report.
- Import mode over local CSVs - no gateway, no workspace, no scheduled refresh. Refresh means
  re-reading the committed marts on this machine. Publishing to the Power BI Service would need a
  data source those services can reach, which is out of scope.
- **The `RepoRoot` parameter is committed empty and must be set after cloning.** A parameter
  default is stored in the file, and an absolute path from the author's machine has no business in
  a public repository; the validator fails the build if one appears. The first refresh on a fresh
  clone fails until it is set, either in Desktop or with
  `python -m src.build_powerbi --repo-root auto`.
- Eight tables are disconnected from the calendar by design, so a date filter does not change
  those visuals. Correct, but surprising until the reason is read.
- The GTM constraint mart carries forecast months only, so actual months show blank capacity by
  design rather than a plotted zero. Deferred revenue and billings are actual periods only; no
  forecast billings series is invented. The commission asset is analytically derived, not
  GL-reconciled - `fact_gl_actuals` is a P&L extract with no balance sheet, the same limitation
  Phase 8 records.
- Segment-level Budget ARR figures are allocations, as in Phase 9 - `fact_budget` carries no
  segment grain for ARR movements. Base's segment figures are always segment-native.
- Mart CSV exports are not byte-stable across rebuilds (row order within ties, and floating-point
  dust from parallel aggregation). This predates Phase 10 and affects the CSVs, not the project:
  the expected-results pack is regenerated from the marts in the same build, and the stated
  tolerances are far wider than that dust.
- No mobile layout. The pages are authored at 1280x720 for a board screen.

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
