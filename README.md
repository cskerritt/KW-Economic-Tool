# Forensic Economic Calculator

Single-user web application for three categories of economic damages: economic
loss (lost earnings), life care plan cost projection, and loss of household
services. See `CLAUDE.md` for architecture, locked methodologies, and build order.

## Status

- Shared engine primitives (`engine/common`): done.
- Economic loss, Tinari algebraic method (`engine/earnings`): done, golden test.
- Life care plan, DED Medical Care Cost Index (`engine/lcp`): done, golden test.
- Loss of household services, DED six-step (`engine/lhhs`): done, golden test.
- Web app: FastAPI + Jinja2/HTMX UI with a form and live result per module
  (`app/`), single-user Google sign-in with email allow-list (`app/auth.py`).
- Exports: xlsx (earnings, LCP) and docx (LHHS) in `exports/`, wired to working
  download buttons on each result.
- Persistence: save, reopen, update, and delete cases (`storage/`). Dual backend:
  Postgres when `DATABASE_URL` is set (production), else a local SQLite file.
  Cases store their canonical inputs and recompute on load.
- Shared compute path (`app/compute.py`): one code path from inputs to results,
  used by the web routes, exports, and the MCP server.
- MCP server (`mcp_server/`): one tool per module so Claude Code can run a full
  calculation through the same engine.
- Deploy: Railway config (`Procfile`, `railway.json`, `runtime.txt`).

## Run the web app

```bash
pip install -e ".[web,export]"
# Local development without Google OAuth configured yet:
AUTH_DISABLED=true SESSION_SECRET=dev uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

For real authentication, create a Google OAuth client (Authorized redirect URI
`https://YOUR_HOST/auth/callback`) and set, instead of AUTH_DISABLED:

```bash
export SESSION_SECRET="a long random string"
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."
export ALLOWED_EMAILS="christophertskerritt@gmail.com"
```

Only emails in `ALLOWED_EMAILS` can sign in. See `app/config.py`.

## Deploy to Railway

The repo includes `Procfile`, `railway.json`, and `runtime.txt`. The start
command runs uvicorn with `--proxy-headers --forwarded-allow-ips=*` so that
behind Railway's TLS-terminating proxy the OAuth callback URL is built as
`https://…` (Google requires an exact, https redirect URI).

1. Create a Railway project from this repo. Nixpacks builds it and runs
   `pip install -e ".[web,export]"` (engine stays dependency-free; web + export
   extras, including reportlab for PDF, are installed).
2. **Persistence — pick one:**
   - *Postgres (recommended):* add the Railway **Postgres** plugin. It injects
     `DATABASE_URL` automatically and the app uses it; no Volume needed.
   - *SQLite:* add a **Volume mounted at `/data`** so saved cases survive
     redeploys and set `DB_PATH=/data/forensic_calc.sqlite`. The app creates the
     DB file's parent directory on first boot.
3. Set environment variables (see `.env.example` for the full annotated list):

   | Variable | Required | Notes |
   |---|---|---|
   | `SESSION_SECRET` | yes | long random string; signs the session cookie |
   | `DATABASE_URL` | for Postgres | injected by the Railway Postgres plugin; selects the Postgres backend |
   | `DB_PATH` | for SQLite | `/data/forensic_calc.sqlite` (the mounted volume); used only when `DATABASE_URL` is unset |
   | `COOKIE_SECURE` | yes | `true` in production (HTTPS-only session cookie) |
   | `GOOGLE_CLIENT_ID` | yes | OAuth 2.0 Web client id |
   | `GOOGLE_CLIENT_SECRET` | yes | OAuth 2.0 Web client secret |
   | `ALLOWED_EMAILS` | yes | comma-separated sign-in allow-list |
   | `FRED_API_KEY` | for LCP helper | enables `/lookups/lcp-growth`; never commit it |
   | `REPORT_FIRM` | optional | PDF report header (e.g. `KW Economics`) |
   | `REPORT_AUTHOR` | optional | PDF signature block |
   | `AUTH_DISABLED` | no | must be unset/false in production |

4. In the Google Cloud OAuth client (Web application), set the authorized
   redirect URI to `https://YOUR_RAILWAY_DOMAIN/auth/callback` and the authorized
   JavaScript origin to `https://YOUR_RAILWAY_DOMAIN`.

The health check path is `/healthz`. After deploy, visit the domain, sign in
with an allow-listed Google account, and confirm Saved cases persist across a
redeploy (proves Postgres via `DATABASE_URL`, or the volume mounted at `DB_PATH`).

## MCP server (Claude Code)

Expose the engine to Claude Code with the same shared compute path:

```bash
pip install -e ".[mcp]"
python -m mcp_server.server
```

Register it in your Claude Code MCP config (stdio), e.g.:

```json
{
  "mcpServers": {
    "forensic-calc": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/forensic-calc"
    }
  }
}
```

Tools: `compute_earnings`, `compute_lcp`, `compute_lhhs`. Each takes the
canonical input dict (decimal rates) and returns the summary plus rows.

## Engine quick start

The engine is pure standard-library Python (no dependencies).

```python
from engine.earnings import (
    EarningsAssumptions, build_earnings_inputs, project_earnings,
)

a = EarningsAssumptions(
    base_earnings=93628.0, base_year=2008,
    start_year=2009, end_year=2022, valuation_year=2015,
    growth_past=0.031, growth_future=0.038, growth_switch_year=2016,
    discount_rate=0.0325,
    worklife=0.919, unemployment=0.035, tax=0.12,
    personal_consumption_initial=0.25, personal_consumption_later=0.20,
    pc_switch_year=2016,
    partial_years={2009: 0.33, 2022: 0.26},
)
result = project_earnings(build_earnings_inputs(a), a.discount_rate, a.valuation_year)
print(round(result.total_present_value, 2))   # 858384.39
```

Run the worked example: `python examples/exposito.py`

## Tests

With pytest installed: `pytest` from the repo root.

Golden-value tests are mandatory and must not be weakened to make a change pass.
