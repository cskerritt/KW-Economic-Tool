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
  earnings/        Tinari algebraic method (incl. personal_injury dual-stream)
  lcp/             DED Medical Care Cost Index method   (phase 3)
  lhhs/            DED replacement-cost six-step method (phase 4)
app/               FastAPI + Jinja2/HTMX UI             (phase 2+)
exports/           xlsx (openpyxl), docx (python-docx), pdf (reportlab)
storage/           SQLite (stdlib sqlite3)              (phase 5)
mcp_server/        optional MCP over the same engine    (phase 5)
datasets/          stdlib loaders/lookups over data/ (incl. FRED for LCP growth)
tests/             pytest golden-value cases; tests/e2e/ Playwright (opt-in)
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
6. (done) personal-injury dual-stream earnings: `engine/earnings/personal_injury.py`
   subtracts a residual stream from a pre-injury stream (both PC=0). A WD case is
   a single stream with the personal-consumption deduction; a PI case carries an
   optional `residual` sub-dict in its canonical inputs. Golden: net = pre - residual.
7. (done) PDF report export: `exports/pdf.py` (reportlab) renders all three
   modules; additive alongside xlsx/docx. `export_result(module, result, fmt=...)`;
   the route passes `fmt=pdf`. Branding via `REPORT_FIRM` / `REPORT_AUTHOR`.
8. (done) LCP growth-rate helper: `datasets/fred.py` fetches BLS CPI series from
   FRED and composes the DED §920 item growth rate (category CAGR - overall CAGR
   + expected general inflation). Endpoint `/lookups/lcp-growth`; needs
   `FRED_API_KEY` (never committed). Network lives only in `datasets/`.
9. (done) Railway deploy hardening: start command runs uvicorn with
   `--proxy-headers --forwarded-allow-ips='*'` so the OAuth callback is built as
   https; `COOKIE_SECURE=true` makes the session cookie HTTPS-only; the DB parent
   dir is created on first boot for the mounted volume. See `.env.example`.

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

`datasets/fred.py` is the one place that makes a network call (stdlib urllib),
and it lives here on purpose so the engine stays offline-pure. It turns FRED CPI
index series into a CAGR and composes the LCP item growth rate via the engine's
`medical_growth_rate`. The category->series map is auditable reference data in
`data/fred/cpi_series.csv`; series ids must be verified to resolve on FRED before
being added. `FRED_API_KEY` is read from the environment and never committed.
Network failures surface as a clean 504 from `/lookups/lcp-growth`, never a 500.

## Persistence
`storage/` is a thin, no-ORM repository with a dual backend chosen at connect
time: a `postgres://`/`postgresql://` `DATABASE_URL` selects Postgres (psycopg,
production — Railway's Postgres plugin injects this, so no Volume is needed);
anything else is a local SQLite file at `DB_PATH` (stdlib sqlite3, local dev and
the default test run). `app/config.py` exposes `settings.db_target` (the URL or
the path); `storage/db.connect` and `init_db` branch on it. The two dialects
differ only in the parameter placeholder (`?` vs `%s`) and the id column type;
`CaseStore` reads new ids back with `RETURNING id` on both, and rows are name-
addressable on both (`sqlite3.Row` / psycopg `dict_row`) so `SavedCase.from_row`
is shared. psycopg is imported lazily, so SQLite-only environments need no extra
dependency. Cases store their canonical inputs (JSON) plus a small summary;
results are recomputed from inputs on load so a case reproduces exactly. The
optional `test_postgres_roundtrip` runs only when `TEST_DATABASE_URL` (a
dedicated var, never the live `DATABASE_URL`) points at a throwaway Postgres db.

## Testing
`pytest` from the repo root. Golden-value tests are mandatory for every engine
module and must not be weakened to make a change pass. If a number changes,
justify it against the source document in the test docstring.

The default `pytest` run is hermetic and fast (no network, no browser); it
deselects `-m e2e` via `addopts`. Browser end-to-end tests live in `tests/e2e/`
(Playwright) and drive the real HTMX UI against a uvicorn server the fixtures
start. Run them with:

```
pip install -e ".[web,export,e2e]"
playwright install chromium
pytest -m e2e            # set FRED_API_KEY to exercise the live LCP helper
```

The e2e FRED test is external-tolerant: it asserts the helper returns a composed
rate OR degrades cleanly (it skips entirely without `FRED_API_KEY`), so it never
flakes on FRED rate limits. The composition math is pinned by offline unit tests
in `tests/test_fred.py`.
