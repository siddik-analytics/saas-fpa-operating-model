# Report captures

Screenshots of the generated reporting layers, used by the repository README and the
[case study](../portfolio_case_study.md).

Every image here is an actual render of the committed project, captured from Power BI Desktop and
Microsoft Excel after the build. Nothing is mocked up, composed or retouched.

## Power BI — [`powerbi/`](powerbi/)

Captured from Power BI Desktop with the `RepoRoot` parameter set locally and the semantic model
refreshed, after the manual visual inspection described in
[the phase document](../powerbi_executive_report.md). The ribbon and all three side panes are
collapsed for the capture, which is what lets a 720 pt page fit the viewport at full width.

| File | Page | What it shows |
|---|---|---|
| [`executive-q2-reforecast.png`](powerbi/executive-q2-reforecast.png) | Executive Q2 Reforecast | The page navigator, eight KPI cards scaled to board precision, the Exit ARR bridge from Budget to Base, Budget-versus-Base ranked by variance, the three scenario ARR paths, policy runway against the 24-month floor, and the rules-generated commentary |
| [`arr-retention.png`](powerbi/arr-retention.png) | ARR, Retention & Renewals | Monthly ARR movement with the forecast line starting where the actual stops, the NRR / GRR / logo-retention trend, movement and retention by segment, acquisition-cohort retention, and forward ATR by quarter |
| [`gtm-capacity-pipeline.png`](powerbi/gtm-capacity-pipeline.png) | GTM Capacity & Pipeline | H2 capacity against pipeline against the constrained figure, the same three series monthly, capacity and conversion by segment, FY2025 unit economics, and the sales-efficiency pair |
| [`financial-performance.png`](powerbi/financial-performance.png) | Financial Performance & Headcount | The management P&L, the Budget-versus-Base scorecard ranked by variance, the operating-income bridge, revenue against gross margin on a fixed band, the accounting balances at the reporting date, and Dec-2026 headcount by function |
| [`segment-detail.png`](powerbi/segment-detail.png) | Segment detail (drill-through) | The hidden sixth page **as a reader arrives at it**, captured after right-clicking the SMB row on page 2 and choosing *Segment detail*. Its figures agree with that row: $4.8M, 84.7%, 76.7%, 78.7%, 534. Shows exit ARR, TTM retention and the customer count behind it, the monthly ARR movement, the retention trend, the forward renewal book and the acquisition cohorts - all filtered to one segment |
| [`plan-scenarios.png`](powerbi/plan-scenarios.png) | Plan & Scenarios | Bear / Base / Bull ARR, then affordability and attractiveness on separate halves of the page, with the Board floor drawn as a reference line and the assumptions stated by driver and segment |

## Excel — [`excel/`](excel/)

Captured from `excel/Helio_SaaS_FP&A_Operating_Model.xlsx` — the reviewed workbook, not the
builder's output (see [the design notes](../excel_operating_model.md)). Each sheet is rendered
through `Range.CopyPicture` over its own declared content edge, so the frame is the page rather
than an arbitrary rectangle around it.

| File | Sheet | What it shows |
|---|---|---|
| [`excel-executive-summary.png`](excel/excel-executive-summary.png) | Executive Summary | Five KPI cards with variance bars, the 36-month Exit ARR hero chart against the Board Budget point, the Budget-to-Base ARR bridge beside runway by path against the 24-month floor, the rules-generated management read, and the decision band where each verdict is a formula over an approved mart |
| [`excel-arr-retention.png`](excel/excel-arr-retention.png) | ARR & Retention | The monthly ARR waterfall with actual and forecast months shaded apart, the TTM NRR / GRR trend against 100%, the segment panel, and the forward renewal book by quarter |
| [`excel-cash-runway.png`](excel/excel-cash-runway.png) | Cash Flow | The H2 cash path, the operating result, the direct-method cash roll-forward, the profit-to-cash bridge, and both runway measures kept separate |
| [`excel-forecast-drivers.png`](excel/excel-forecast-drivers.png) | Forecast Drivers | The single scenario selector, every driver it resolves with its ratio to Base, and the opening position the forecast builds from |
| [`excel-scenarios.png`](excel/excel-scenarios.png) | Scenarios | The five management levers measured from Base, the Bear / Base / Bull comparison, and the multipliers themselves marked as inputs |
| [`excel-pl-budget-vs-base.png`](excel/excel-pl-budget-vs-base.png) | P&L | Board Budget against Base reforecast by P&L line, with centrally derived favourability, and Dec-2026 headcount by function |
| [`excel-budget-bridge.png`](excel/excel-budget-bridge.png) | Budget Bridge | The Budget-to-Base operating income walk with a running balance and a residual that must read zero, gross margin reported in basis points, and the revenue decomposition. Framed on those three sections: the sheet is 204 rows, and a full-page render of it is 1:3.6 |

## Recapturing

Recapture whenever a change alters what a page displays — a format, a column, a layout or a visual.
A capture that shows a defect since fixed misrepresents the current build.

Capture at 100% scaling with the report fitted to the page, and exclude Windows chrome, the
Desktop ribbon and the page-tab strip.

Every image here then passes through the padding standard —
5% of the long edge on all four sides, floored at 40 px and capped at 96 px, on a neutral drawn
from the artefact's own palette (white for Excel, the `#F7F8FA` page background for Power BI).
The source is placed at 1:1 and the canvas grows around it: nothing here is upscaled, stretched
or cropped to fit a ratio.
