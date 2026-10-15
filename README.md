# PACE — Permionics Advanced Calculation Engine

**PACE** is a professional-grade membrane process design tool developed for Permionics Membranes Pvt. Ltd. It enables engineers to design, simulate, and report on Reverse Osmosis (RO), Nanofiltration (NF), and Ultrafiltration (UF) systems.

---

## Features

- **Intelligent Process Recommendation** — Automatically selects the optimal membrane technology and configuration based on feed water quality and project targets.
- **Full RO/NF System Design** — Multi-stage, multi-pass system design with element-level flux, pressure, and recovery calculations.
- **Scaling & Fouling Analysis** — PHREEQC-powered saturation index calculations for gypsum, calcium carbonate, silica, and other foulants.
- **Membrane Aging Models** — Physics-based aging predictions for permeability, salt rejection, and energy consumption over the plant lifetime.
- **Chemical Conditioning** — pH adjustment, antiscalant dosing, and CO₂ degassing simulation.
- **UF Pre-treatment Sizing** — Full UF module sizing, flux normalization, and backwash scheduling.
- **Automated PDF Reports** — One-click professional report generation with charts, tables, and project metadata.

---

## Architecture

```
PACE_v1/
├── backend/            # Python FastAPI server — all calculation engines
├── ui_ux_design/       # Frontend — HTML / CSS / JS single-page application
├── docs/               # Technical documentation and SOPs
├── tests/              # Automated test suite
├── Dockerfile          # Cloud deployment (Railway)
├── PACE.spec           # PyInstaller spec — Windows executable
└── build_exe.bat       # Build script for the Windows executable
```

### Entry Points

| Mode | Command |
|---|---|
| **Cloud / Railway** | `python backend/run_cloud.py` (reads `PORT` env var, binds `0.0.0.0`) |
| **Desktop / Local** | `python backend/run_desktop.py` (auto-finds free port, opens browser) |
| **Windows EXE** | `dist/PACE_Permionics.exe` (self-contained, no Python required) |

---

## Setup & Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
python backend/run_desktop.py
```

The app will automatically open in your default browser.

---

## Building the Windows Executable

```batch
build_exe.bat
```

The compiled executable will be placed in `dist/PACE_Permionics.exe`.

---

## Cloud Deployment

The application is deployed on **Railway** using the included `Dockerfile`. Any push to the `railway_deployment` branch triggers an automatic redeploy.

---

## Documentation

See the `docs/` folder for:
- `technical_documentation.md` — Full technical reference
- `codebase_documentation.md` — Module-level code documentation
- `aging_models.md` — Membrane aging physics documentation
- `membrane_aging_sop.md` — Standard operating procedure for aging analysis
- `commercial_readiness.md` — Gap analysis for commercial deployment
- `uf_sizing_sop.md` — UF sizing logic and SOP

---

*Developed internally for Permionics Membranes Pvt. Ltd.*
