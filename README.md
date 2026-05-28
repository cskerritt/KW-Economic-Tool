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
- Persistence: save, reopen, update, and delete cases (`storage/`, stdlib
  sqlite3). Cases store their canonical inputs and recompute on load.
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

The repo includes `Procfile`, `railway.json`, and `runtime.txt`.

1. Create a Railway project from this repo.
2. Add a Volume mounted at `/data` (so saved cases survive redeploys).
3. Set environment variables: `SESSION_SECRET`, `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, `ALLOWED_EMAILS`, and `DB_PATH=/data/forensic_calc.sqlite`.
4. In the Google OAuth client, set the redirect URI to
   `https://YOUR_RAILWAY_DOMAIN/auth/callback`.

The health check path is `/healthz`.

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
