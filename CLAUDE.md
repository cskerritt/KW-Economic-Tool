# Forensic Economic Calculator

A single-user web application that computes three categories of economic damages:
economic loss (lost earnings), life care plan (LCP) cost projection, and loss of
household services (LHHS). Built and maintained with Claude Code.

## Architecture: engine first

The calculation **engine** (`engine/`) is pure standard-library Python with no
runtime dependencies. It is the product. Everything else imports it:

```
engine/            pure math, fully unit-tested, no web/db deps
  common/          present value, growth, discounting, shared assumptions
  earnings/        Tinari algebraic method
  lcp/             DED Medical Care Cost Index method   (phase 3)
  lhhs/            DED replacement-cost six-step method (phase 4)
app/               FastAPI + Jinja2/HTMX UI             (phase 2+)
exports/           xlsx (openpyxl) and docx (python-docx) (phase 3+)
storage/           SQLite via SQLModel                  (phase 5)
mcp_server/        optional MCP over the same engine    (phase 5)
tests/             pytest, golden-value cases
```

Rule: the web layer, exports, and MCP NEVER do math. They build typed inputs,
call the engine, and render the typed result. Every displayed number traces to
an input, a formula, and a cited source.

## Locked methodologies (do not substitute)

These are fixed by the source documents and must not be swapped for alternatives
without an explicit decision recorded here.

### Economic loss: Tinari algebraic method
Source: Frank D. Tinari, "Demonstrating Lost Earnings: Algebraic vs. Spreadsheet
Method," The Earnings Analyst, Vol. 15, 2016.

Adjusted Income Factor applied to grown gross earnings, then discounted:

```
AIF = { [ (GE x WLE)(1 - UF) ] (1 - TL) } (1 - PC)              # no fringe
AIF = { [ (GE x WLE)(1 - UF) ](1 + FB) - [ (GE x WLE)(1 - UF) ](TL) } (1 - PC)   # with fringe
```

GE gross earnings, WLE worklife-to-retirement ratio, UF unemployment factor,
TL tax rate, PC personal consumption, FB fringe rate. Order is fixed: worklife,
unemployment, (fringe added pre-tax, tax applied to wages only), tax, personal
consumption. Personal consumption is deducted in wrongful death only; for
personal injury set PC = 0 and compute pre-injury minus residual capacity.
Past years undiscounted; future years discounted at the net discount rate.

Golden test: the paper's worked example reproduces AIF = 58.53% (PC 25%) and
62.43% (PC 20%) and a total present value of ~$858,387.

### Life care plan: DED Medical Care Cost Index  (phase 3)
Source: Determining Economic Damages (Prakash-Canjels), Chapter 9 §920 and §903.
Item growth = real medical inflation (matched CPI category inflation minus
overall CPI inflation) + expected general inflation (CBO CPI projection). Each
LCP category carries its own growth rate. Grow each item across its frequency
and replacement cycle from start to stop (often to life expectancy), discount to
present value, sum per category and a lifetime total.

### Loss of household services: DED replacement-cost six-step method  (phase 4)
Source: Determining Economic Damages, Chapter 6.
Replacement (specialist) cost using Expectancy Data Dollar Value of a Day (DVD)
weekly hours by demographic, valued at embedded OES wages, annualized x 365.25,
optional Table 414 area-wage adjustment, demographic life-cycle updates,
declining-health and self-consumption adjustments, then discount to present value.

Cross-module guardrail: attendant/home care can appear in both LCP and LHHS.
Flag overlapping LCP items so they can be netted out of LHHS (avoid double count).

## Data sources referenced by the methods
- Worklife expectancy: Skoog-Ciecka-Krueger tables.
- Life expectancy: NVSR state life tables.
- Fringe benefits: BLS Employer Costs for Employee Compensation (ECEC).
- Growth/discount assumptions: SPF and/or CBO projections.
- Personal consumption: Patton-Nelson (wrongful death).
- Household services hours/values: Expectancy Data Dollar Value of a Day (DVD).
- Medical price growth: BLS CPI Detailed Report by category; CBO CPI projection.

## Conventions
- Money as float during calculation; round only for display.
- Rates are decimals (0.0325 not 3.25). Document units on every field.
- Engine inputs/outputs are dataclasses (stdlib). pydantic is used only at the
  API boundary in `app/`.
- Snapshot all assumptions with each saved result so a case reproduces exactly
  even after default rates are updated later.

## Build order
1. (done) common engine + earnings module + golden test.
2. (done) earnings FastAPI route + HTMX page; single-user Google sign-in.
3. (done) lcp module + xlsx export.
4. (done) lhhs module + docx report export.
5. (done) SQLite persistence of saved cases (stdlib sqlite3, `storage/`),
   wired export downloads, Railway deploy config, MCP server (`mcp_server/`).

## Shared compute path
`app/compute.py` is the single place that turns a canonical input dict (DECIMAL
rates) into an engine result and a summary. The web routes, export downloads,
and MCP server all call it, so there is one code path to the math. When adding
a module or input, update `app/compute.py` and keep its golden test in
`tests/test_compute.py` aligned with the engine golden tests.

## Reference data layer
`data/` holds CSVs scraped from the source PDFs (see `data/README.md`).
`datasets/` (stdlib only) loads those CSVs and exposes typed lookups: DVD
household-production hours and Table 414 area-wage factors, SCK worklife/YFS,
NVSR life expectancy, ECEC fringe rates, SPF long-term assumptions. The engine
stays pure; `datasets/builders.py` turns lookups into canonical engine inputs
(e.g. an LHHS input dict from a DVD table number plus a residence). The MCP
server exposes the lookups as `lookup_*` tools.

## Persistence
`storage/` is stdlib sqlite3 (no ORM dependency). Cases store their canonical
inputs (JSON) plus a small summary; results are recomputed from inputs on load
so a case reproduces exactly. Set `DB_PATH` to a mounted volume in production.

## Testing
`pytest` from the repo root. Golden-value tests are mandatory for every engine
module and must not be weakened to make a change pass. If a number changes,
justify it against the source document in the test docstring.
