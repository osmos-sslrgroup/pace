# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PACE (Permionics Advanced/Analytical Calculation Engine) is a membrane-process design tool
for RO/NF/UF systems. A FastAPI backend exposes calculation engines; a vanilla-JS single-page
app (`ui_ux_design/`) is the UI. The same backend runs three ways: as a cloud server, a local
desktop app that opens a browser, and a self-contained Windows `.exe`.

## Running & building

```bash
pip install -r requirements.txt

python backend/run_desktop.py   # local dev: auto-picks a free port, opens browser, 127.0.0.1 only
python backend/run_cloud.py     # cloud: binds 0.0.0.0, reads PORT env var, for Docker/Render/Railway
build_exe.bat                   # Windows .exe via PyInstaller (PACE.spec) -> dist/PACE_Permionics.exe
```

Both `run_*.py` mount `ui_ux_design/` as static files at `/` (so the API and UI are served from
one origin). `run_desktop.py` also sets `PHREEQPYTHON_DB` when frozen by PyInstaller.

**Working directory matters.** Backend modules import each other flat (`from system_engine import SystemEngine`),
so Python must run with `backend/` on `sys.path` — i.e. launched via the `run_*.py` entry points, or
with the CWD set to `backend/`. Don't convert these to package-relative imports without updating all call sites.

## Auth

Every HTTP request passes through `BasicAuthASGIMiddleware` (HTTP Basic). Credentials come from env vars
`API_USERNAME` / `API_PASSWORD`; the fallback defaults are hardcoded in `BasicAuthASGIMiddleware` (`backend/server.py`) — set the env vars in any real deployment rather than relying on them.
CORS is wide open (`allow_origin_regex=".*"`) because the auth gate is the real boundary.

## Tests

Tests are **standalone scripts, not a pytest suite** — each runs and prints results:

```bash
cd backend && python ../tests/test_api.py          # in-process: calls _run_projection_core + SystemEngine directly
cd backend && python ../tests/test_autobalance.py  # in-process: ion-balance endpoint
cd backend && python ../tests/test_report.py        # in-process: generates a .docx report
python tests/test_physics.py                        # over HTTP: needs a running server on :8000 + valid Basic auth
```

Note: `tests/test_physics.py` hardcodes `Authorization: Basic user:password123`, which does **not** match the
current default credentials — update the header before relying on it.

## Architecture

Request flow: `server.py` (FastAPI routes + Pydantic models) → `SystemEngine` (orchestrator) →
`ROEngine` / `UFEngine` + `MembraneDatabase`. Key modules in `backend/`:

- **`server.py`** — the live API. All endpoints, Pydantic schemas, auth, and report/PDF plumbing.
- **`system_engine.py`** — `SystemEngine.calculate_system()` dispatches on `technology_train`
  (`RO`, `2P-RO`, `NF`, `UF_RO`, …) and orchestrates element-wise calculations + NF concentrate scaling.
- **`calc_engine.py`** — `ROEngine`: Solution-Diffusion / Spiegler-Kedem transport, osmotic pressure, element-wise simulation.
- **`uf_engine.py`** — UF module sizing, flux, backwash.
- **`membrane_database.py`** — the Permionics RO/NF/UF product catalog **as code** (not a data file).
  Add/edit membranes here; `MembraneRecommender` and `/api/auto-select-membrane` read from it.
- **`physics_aging_engine.py`** — `PhysicsAgingEngine`: rigorous multi-year fouling/scaling/compaction projection
  (cake, biofouling, CNT scaling, NOM, compaction; CIP kinetics; ASTM D4516 normalization). Spec PACE-FEAT-MPP-002.
- **`aging_engine.py`** — **DEPRECATED.** Retained for reference only; nothing in production calls it.
- **`process_engine.py`** — `ProcessRecommendationEngine`: picks technology/config from feed quality + targets.
- **`conditioning.py`** — pH adjustment / antiscalant / CO₂ degassing.
- **`report_generator.py`** — builds the WAVE-style `.docx` report (python-docx + matplotlib charts rendered via Agg).
- **`server_impl.py`** — a stale Vercel-targeted variant of `server.py` (adds a `sys.path` fix and optional
  phreeqpython import). **Not imported anywhere** — edit `server.py`, not this.

### Critical invariant: one projection core

The **Membrane Aging** tab (`/api/simulate-aging`) and the **Year-wise Projection** tab
(`/api/calculate-system-physics`) must produce identical numbers for the same scenario. This is enforced
structurally: both endpoints funnel through the single `_run_projection_core(...)` function in `server.py`,
which builds identical inputs to `PhysicsAgingEngine`. When changing projection logic, keep this single
entry point — do not fork per-endpoint paths.

### Report PDF conversion (platform-dependent)

`report_generator.py` emits `.docx`. The `/api/generate-calculation-report` endpoint converts it to PDF with
a cascade: `docx2pdf` on Windows (`sys.platform == "win32"`), `libreoffice --headless` on Linux/Docker, and
`pymupdf` (`fitz`) as a watermark/fallback path. The Dockerfile installs `libreoffice` for this reason.

### PHREEQC

Scaling/saturation-index chemistry uses `phreeqpython` (`PhreeqPython(database='phreeqc.dat')`, plus bundled
`backend/llnl.dat`). PyInstaller builds collect it via `collect_all('phreeqpython')` in `PACE.spec`, and
`run_desktop.py` points `PHREEQPYTHON_DB` at the extracted DB when frozen.

### Frontend

`ui_ux_design/index.html` (~2.3k lines) + `script.js` (~6.9k lines) — a single-page vanilla-JS app, no build step.
The UI gates a linear workflow via `pace-locked-tab`: Project Details → Feed Data → Scaling → Process → Calculation → Report.
`ui_ux_design/build/` holds older per-screen HTML fragments; the live app is the top-level `index.html`.

## Deployment

Containerized via `Dockerfile` (python:3.11-slim + libreoffice), started with `python backend/run_cloud.py`.
The most recent commit targets Render; the README mentions Railway (auto-redeploy on the `railway_deployment` branch).

## Docs

`docs/` holds the authoritative specs: `technical_documentation.md`, `codebase_documentation.md`,
`aging_models.md`, `membrane_aging_sop.md`, `uf_sizing_sop.md`, `commercial_readiness.md`.
Consult `aging_models.md` / the PACE-FEAT-MPP-002 spec before changing `physics_aging_engine.py`.
