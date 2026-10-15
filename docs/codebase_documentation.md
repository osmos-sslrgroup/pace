# PACE Codebase Documentation
## Permionics Advanced Calculation Engine — Complete Technical Reference

> **Version:** Deployed Production Build (July 2026)
> **Audience:** Developers, engineers, and technical managers who need to maintain, modify, or extend the PACE software.
> **Scope:** Full backend codebase, API layer, membrane database, calculation engines, aging models, economics, and report generation.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Technology Stack & Dependencies](#3-technology-stack--dependencies)
4. [Deployment & Entry Point](#4-deployment--entry-point)
5. [Module Reference](#5-module-reference)
   - [5.1 server.py — API Gateway](#51-serverpy--api-gateway)
   - [5.2 system_engine.py — Orchestration Engine](#52-system_enginepy--orchestration-engine)
   - [5.3 calc_engine.py — RO/NF Element Simulation](#53-calc_enginepy--ronf-element-simulation)
   - [5.4 uf_engine.py — Ultrafiltration Engine](#54-uf_enginepy--ultrafiltration-engine)
   - [5.5 membrane_database.py — Membrane Catalog](#55-membrane_databasepy--membrane-catalog)
   - [5.6 process_engine.py — Process Recommendation Engine](#56-process_enginepy--process-recommendation-engine)
   - [5.7 membrane_recommender.py — Membrane Selection Engine](#57-membrane_recommenderpy--membrane-selection-engine)
   - [5.8 conditioning.py — Interstage pH Conditioning](#58-conditioningpy--interstage-ph-conditioning)
   - [5.9 physics_aging_engine.py — Multi-Year Projection Engine](#59-physics_aging_enginepy--multi-year-projection-engine)
   - [5.10 aging_engine.py — Legacy Engine (Deprecated)](#510-aging_enginepy--legacy-aging-engine-deprecated)
   - [5.11 report_generator.py — PDF Report Generator](#511-report_generatorpy--pdf-report-generator)
   - [5.12 run_app.py — Application Entry Point](#512-run_apppy--application-entry-point)
6. [API Endpoint Reference](#6-api-endpoint-reference)
7. [Data Models (Pydantic Schemas)](#7-data-models-pydantic-schemas)
8. [Technology Trains — Data Flow](#8-technology-trains--data-flow)
   - [8.1 RO (Single-Pass)](#81-ro-single-pass)
   - [8.2 UF+RO](#82-ufro)
   - [8.3 2P-RO (Two-Pass RO)](#83-2p-ro-two-pass-ro)
   - [8.4 UF+2P-RO](#84-uf2p-ro)
   - [8.5 NF and UF+NF](#85-nf-and-ufnf)
   - [8.6 Concentrate Recycle Loop](#86-concentrate-recycle-loop)
9. [Key Calculation Algorithms](#9-key-calculation-algorithms)
   - [9.1 Osmotic Pressure (van't Hoff)](#91-osmotic-pressure-vant-hoff)
   - [9.2 Temperature Correction Factor (TCF)](#92-temperature-correction-factor-tcf)
   - [9.3 Concentration Polarization (Beta)](#93-concentration-polarization-cp--beta)
   - [9.4 Spiegler-Kedem Solute Transport](#94-spiegler-kedem-solute-transport)
   - [9.5 Pressure Drop (Schock-Miquel)](#95-pressure-drop-schock-miquel)
   - [9.6 Interstage Booster Pump Sizing](#96-interstage-booster-pump-sizing)
   - [9.7 Feed Pressure Solver (Bisection)](#97-feed-pressure-solver-bisection)
   - [9.8 Charge Balance Error & Auto-Balance](#98-charge-balance-error-cbe--auto-balance)
   - [9.9 PHREEQC Scaling Indices](#99-phreeqc-scaling-indices-si)
   - [9.10 NF Concentrate Scaling (Davies)](#910-nf-concentrate-scaling-davies)
10. [Physics Aging Model Details](#10-physics-aging-model-details)
    - [10.1 Sub-model I — Cake/Colloid Filtration](#101-sub-model-i--cake--colloid-filtration-rk4)
    - [10.2 Sub-model II — Biofouling (Monod)](#102-sub-model-ii--biofouling-monod)
    - [10.3 Sub-model III — Inorganic Scaling (CNT)](#103-sub-model-iii--inorganic-scaling-cnt)
    - [10.4 Sub-model IV — NOM Adsorption (Langmuir)](#104-sub-model-iv--nom-adsorption-langmuir)
    - [10.5 Sub-model V — Membrane Compaction](#105-sub-model-v--membrane-compaction-kelvin-voigt)
    - [10.6 Salt Permeability Degradation](#106-salt-permeability-degradation)
    - [10.7 CIP Kinetics](#107-cip-kinetics)
    - [10.8 ASTM D4516-19a Normalisation](#108-astm-d4516-19a-normalisation)
11. [Economic Analysis Model](#11-economic-analysis-model)
12. [Membrane Database Schema](#12-membrane-database-schema)
    - [12.1 RO/NF Membrane Fields](#121-ronf-membrane-fields)
    - [12.2 UF Module Fields](#122-uf-module-fields)
13. [Authentication & Security](#13-authentication--security)
14. [Extension Guide — How to Add New Features](#14-extension-guide--how-to-add-new-features)
    - [14.1 Adding a New RO/NF Membrane](#141-adding-a-new-ronf-membrane)
    - [14.2 Adding a New UF Module](#142-adding-a-new-uf-module)
    - [14.3 Adding a New Technology Train (Similar to Existing)](#143-adding-a-new-technology-train-similar-to-existing)
    - [14.4 Adding a Completely New Technology Train](#144-adding-a-completely-new-technology-train)
    - [14.5 Adding a New Scalant to PHREEQC Calculations](#145-adding-a-new-scalant-to-the-phreeqc-calculations)
    - [14.6 Adding a New Feed Water Ion Parameter](#146-adding-a-new-feed-water-ion-parameter)
    - [14.7 Adding a New Fouling Sub-Model to the Aging Engine](#147-adding-a-new-fouling-sub-model-to-the-aging-engine)
    - [14.8 Adding a New Economic Parameter](#148-adding-a-new-economic-parameter)
    - [14.9 Adding a New API Endpoint](#149-adding-a-new-api-endpoint)
    - [14.10 Modifying the Report Output](#1410-modifying-the-report-output)
15. [File Map Quick Reference](#15-file-map-quick-reference)
16. [Glossary](#16-glossary)

---

## 1. System Overview

PACE (Permionics Advanced Calculation Engine) is a physics-based web application for designing, sizing, and projecting the performance of membrane-based water treatment systems, developed by Permionics Membranes Pvt. Ltd.

| Capability | Description |
|---|---|
| Feed Water Analysis | Accepts full ionic profiles; runs PHREEQC thermodynamic equilibrium to compute Saturation Indices for 9 mineral phases |
| Process Recommendation | Automatically recommends the technology train (RO, NF, UF+RO, 2P-RO) based on feed water quality |
| System Sizing | Sizes UF modules, RO/NF stages, vessels, and elements; bisection-solves for required feed pressure |
| Technology Trains | Supports RO, UF+RO, NF, UF+NF, 2P-RO, UF+2P-RO, and concentrate recycle loops |
| Membrane Selection | Multi-criteria scoring to recommend the best Permionics membrane for a given application |
| Performance Projection | Physics-based 5-year projection of NPF, NSP, SEC decline using 5 fouling sub-models |
| Economic Analysis | CAPEX and OPEX breakdown, annualised cost per kL calculation |
| PDF Reports | WAVE-style formatted calculation reports generated as `.docx` then converted to `.pdf` |
| Auto-Balance | Electroneutrality balancing (CBE) of feed water ion analysis |

---

## 2. Architecture Diagram

```
+-----------------------------------------------------+
|             Frontend  (ui_ux_design/)               |
|      HTML / CSS / JS  served as static files        |
|   Sends JSON payloads <-> receives JSON results     |
+------------------------+----------------------------+
                         |  HTTP/REST (Basic Auth)
                         v
+-----------------------------------------------------+
|         server.py   (FastAPI API Gateway)           |
|  Routes requests -> engines -> returns results      |
|  Also runs PHREEQC concentrate SI post-solve        |
+---+----------+----------+----------+---------------+
    |          |          |          |
    v          v          v          v
system_    process_   membrane_   report_
engine.py  engine.py  recommender generator.py
    |                 .py
    +---> calc_engine.py       (ROEngine — element simulation)
    +---> uf_engine.py         (UFEngine — UF sizing)
    +---> conditioning.py      (pH adjustment between 2P-RO passes)
    +---> physics_aging_engine.py  (PhysicsAgingEngine)
                  |
                  +---> calc_engine.py (used internally for aged sims)

All engines read from:
    membrane_database.py  (MembraneDatabase — static catalog)

External services:
    phreeqpython / PHREEQC  (thermodynamic equilibrium solver)
    LibreOffice (headless PDF conversion on Linux/Docker)
    PyMuPDF / fitz  (PDF watermarking)
```

---

## 3. Technology Stack & Dependencies

| Component | Technology |
|---|---|
| Web Framework | FastAPI (Python) |
| ASGI Server | Uvicorn |
| Data Validation | Pydantic v2 |
| Thermodynamics | phreeqpython (wraps USGS PHREEQC) |
| Report Generation | python-docx |
| PDF Conversion | LibreOffice (Linux/Docker), docx2pdf (Windows) |
| PDF Watermarking | PyMuPDF (fitz) |
| Authentication | Custom ASGI Basic Auth Middleware |
| Frontend | Vanilla HTML + CSS + JavaScript (static files) |
| Containerisation | Docker (python:3.11-slim base image) |

**`requirements.txt`:**
```
fastapi
uvicorn
phreeqpython
pydantic
matplotlib
numpy
python-docx
pymupdf
```

---

## 4. Deployment & Entry Point

### Docker (Production — Linux)

The `Dockerfile` at the project root:
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y libreoffice gcc g++ python3-dev
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "backend/run_app.py"]
```
- **libreoffice** is required for headless DOCX -> PDF conversion.
- App listens on `$PORT` (default 8000).

### Local Windows Development

```bat
cd backend
python run_app.py
```
- Opens browser automatically at `http://127.0.0.1:8000` (skipped when `RAILWAY_PROJECT_ID` or `PORT` env vars are set).
- PDF conversion uses `docx2pdf` on Windows.

### Entry Point: `backend/run_app.py`

```python
from server import app
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
uvicorn.run(app, host="0.0.0.0", port=port)
```

`run_app.py` imports the FastAPI `app` from `server.py`, mounts `ui_ux_design/` as a static files root, and starts Uvicorn. This means:
- All API calls go to `/api/...` routes defined in `server.py`.
- Root URL `/` serves the frontend `index.html`.

> **Important:** The PHREEQC database file (`phreeqc.dat` / `llnl.dat`) lives in `backend/`. The working directory must be `backend/` when `server.py` is imported, or `phreeqpython.PhreeqPython(database='phreeqc.dat')` will fail to initialise.

---

## 5. Module Reference

### 5.1 `server.py` — API Gateway

**Location:** `backend/server.py` (~1,325 lines)

**Role:** Defines all HTTP endpoints using FastAPI. Instantiates engines, orchestrates multi-engine calls, runs PHREEQC concentrate Saturation Index calculations post-solve, and returns structured JSON responses.

**Key responsibilities:**
- Defines all Pydantic request/response models (see Section 7).
- Implements `BasicAuthASGIMiddleware` to protect all `/api/` routes.
- Initialises a single global `phreeqpython.PhreeqPython` instance (`pp`). **Only one instance should ever exist per process** — do not create additional instances.
- Defines `_run_projection_core()` — the **shared internal function** called by BOTH `/api/simulate-aging` and `/api/calculate-system-physics`. This design prevents any divergence between the Aging tab and the Year-wise Projection tab.
- After every `calculate-system` call, builds a PHREEQC solution from concentrate ion concentrations and reads back Calcite, Aragonite, Gypsum, Barite, etc. Saturation Indices. Always calls `sol.forget()` to prevent PHREEQC memory leaks.

**Critical design rules:**
1. The PHREEQC instance `pp` is module-level. Never create a second one.
2. `_run_projection_core()` is the single source of truth for physics projections — both endpoints call it; never fork the logic.
3. All `sol.forget()` calls are mandatory after every PHREEQC solution use.

---

### 5.2 `system_engine.py` — Orchestration Engine

**Location:** `backend/system_engine.py` (~995 lines)

**Role:** Routes requests to the appropriate sub-engine and assembles the final result dictionary.

**Class:** `SystemEngine`

| Method | Purpose |
|---|---|
| `calculate_system(input_data)` | Standard single-pass simulation. Detects UF and/or RO/NF from `technology_train`. Bisects feed pressure to hit `target_recovery_pct`. Calls `UFEngine.simulate_uf()` if `"UF"` in train, then `ROEngine.simulate_system()`. |
| `calculate_system_with_recycle(input_data)` | Wraps `calculate_system()` with an iterative concentrate-recycle loop. Blends fresh feed with recycled concentrate at ratio `recycle_ratio`. Iterates up to 15 times until permeate flow converges within 0.2%. |
| `simulate_two_pass_system(input_data)` | Runs Pass 1 RO, applies interstage conditioning via `conditioning.py`, auto-sizes Pass 2 vessels, runs Pass 2 RO. Optionally loops for concentrate recycle from Pass 2 back to Pass 1. |
| `_calculate_two_pass_economics(...)` | Calculates combined CAPEX/OPEX for a 2-pass system. |

**Module-level helper:** `_compute_nf_concentrate_scaling(conc_ions, feed_ph, temp_c)` calculates Saturation Indices for NF-specific scalants (CaSO4, BaSO4, SrSO4, CaF2, SiO2, CaCO3) using the Davies ionic-strength correction. Called when the train includes NF.

**Feed pressure solver (bisection loop inside `calculate_system`):**
```python
for _ in range(25):
    mid_p = (low_p + high_p) / 2.0
    ro_res = self.ro_engine.simulate_system(feed_flow, mid_p, ions, ...)
    rec = ro_res["summary"]["total_recovery"]
    if abs(rec - target_recovery) < 0.005: break
    if rec < target_recovery: low_p = mid_p
    else: high_p = mid_p
```

---

### 5.3 `calc_engine.py` — RO/NF Element Simulation

**Location:** `backend/calc_engine.py` (~659 lines)

**Role:** Implements element-level and system-level mass transport simulation using the Solution-Diffusion model (RO) and the Spiegler-Kedem model (RO and NF).

**Class:** `ROEngine`

| Method | Purpose |
|---|---|
| `_calculate_osmotic_pressure(ions, temp_c)` | van't Hoff equation with TDS-dependent osmotic coefficient phi (0.90–1.0) |
| `_calculate_tcf(temp_c, E_Aw_over_R)` | Arrhenius TCF. Uses membrane-specific `E_Aw/R` for NF; uses legacy U=2640/3020 split for RO. |
| `_calculate_cp_beta(flux_lmh, ...)` | Concentration Polarization factor beta = Cm/Cb using Schock-Miquel Sh = 0.04 Re^0.75 Sc^0.33 |
| `_calculate_pressure_drop(...)` | Pressure drop per element using Schock-Miquel friction: lambda = 6.23 Re^-0.3 |
| `simulate_element(...)` | Iterative self-consistent solver for a single 8040 element. Converges flux, CP, permeate concentrations, and NDP simultaneously. Applies Donnan electroneutrality correction for NF. |
| `simulate_system(...)` | Loops over stages and elements. Manages vessel-parallel flow splitting, interstage booster pump sizing, and aggregates permeate and concentrate streams. |

**Ion diffusivities used for CP calculation (weighted average):**
```python
D_AB_ions = {
    'Na': 1.33e-9, 'Cl': 2.03e-9, 'Ca': 0.79e-9, 'Mg': 0.71e-9,
    'SO4': 1.07e-9, 'HCO3': 1.19e-9, 'K': 1.96e-9,
    'B': 1.10e-9, 'NO3': 1.90e-9
}  # units: m^2/s at 25 degC
```

---

### 5.4 `uf_engine.py` — Ultrafiltration Engine

**Location:** `backend/uf_engine.py` (~142 lines)

**Role:** Sizes a UF system, calculates TMP (clean and fouled), backwash losses, system recovery, and generates operating limit warnings.

**Class:** `UFEngine`

| Method | Purpose |
|---|---|
| `_viscosity_correction(temp_c)` | Arrhenius viscosity ratio relative to 20 degC |
| `simulate_uf(...)` | Full UF simulation. Computes number of modules, actual filtration flux, backwash/flush losses, net product flow, clean TMP at design/min/max temperatures, and seven operating limit warnings. |

**UF operating cycle (fixed in engine):**

| Parameter | Value |
|---|---|
| Filtration duration | 90 min |
| Backwash duration | From module database `backwash_duration_s` |
| Forward flush | 1 min per cycle (50% safety factor on `min_forward_flush_m3h`) |
| Acid CEB interval | 168 h (weekly) |
| Alkali CEB interval | 168 h (weekly) |
| CIP interval | 90 days |

**Key note:** The UF engine is "intake-limited". It uses `gross_feed_flow_m3h` as a fixed input. The net product after backwash losses is what feeds downstream RO/NF. Feed TDS and ionic composition are **unchanged** by UF (dissolved salts pass freely through UF membranes).

---

### 5.5 `membrane_database.py` — Membrane Catalog

**Location:** `backend/membrane_database.py` (~1,222 lines)

**Role:** Static Python dictionary database of all membrane and UF module specifications. The single source of truth for membrane transport parameters used by the calculation engines.

**Class:** `MembraneDatabase`

**RO/NF membranes in catalog:**

| Model ID | Type | Manufacturer | Area (m2) | Notes |
|---|---|---|---|---|
| `BW30-400` | BWRO | DuPont | 37.2 | Industry reference |
| `SW30HRLE-400` | SWRO | DuPont | 37.2 | High-rejection seawater |
| `CPA5-LD` | BWRO | Hydranautics | 37.2 | Low differential pressure |
| `HPA-4040` | BWRO | Permionics | 9.3 | 4x40 element |
| `HPA-RO-8040-LF-WW` | BWRO | Permionics | 37.2 | Low-fouling, wastewater |
| `HPA-RO-8040` | BWRO | Permionics | 37.2 | Standard BWRO |
| `HPA-RO-LPM-8040-440` | BWRO | Permionics | 40.9 | Low pressure, large area |
| `HPARO-8040-BW-400` | BWRO | Permionics | 37.2 | Standard |
| `HPARO-8040-LF` | BWRO | Permionics | 37.2 | Low-fouling |
| `HPARO-8040-LF2` | BWRO | Permionics | 37.2 | Low-fouling v2 |
| `HPARO-8040-PRO-400` | BWRO | Permionics | 37.2 | Pro series |
| `SWRO-8040-400` | SWRO | Permionics | 37.5 | Max pressure 55.2 bar |
| `SWRO-FR-8040-400` | SWRO | Permionics | 37.2 | Fouling-resistant |
| `SWRO-HLE-8040-400` | SWRO | Permionics | 37.2 | High-low-energy |

**UF modules in catalog (all Permionics PERMA-UF-*):**
`i0875s40, iH0860, 0697, i1066, 2860T, i0975, 0776, i1066X, i0876s, 0697X, iP70, 2880T, 2880, P77, 2880X, i1077, iP80, i1183, 1075T, 0992` (active membrane areas range from 40 m2 to 120 m2).

**Class methods:**

| Method | Returns |
|---|---|
| `get_ro_membrane(name)` | Single membrane dict (falls back to `BW30-400` if not found), normalised via `_normalize_membrane()` |
| `get_uf_module(name)` | Single UF module dict (falls back to `PERMA-UF-i0875s40`) |
| `list_ro_membranes()` | List of dicts with key fields for the frontend dropdown |
| `list_uf_modules()` | List of `{id, name, area}` for the frontend |
| `_normalize_membrane(raw_mem)` | Adds `membrane_class`, `operating_limits`, `surface_class`, `design_flux_table`, `saturation_limits` keys ensuring a uniform schema |

---

### 5.6 `process_engine.py` — Process Recommendation Engine

**Location:** `backend/process_engine.py` (~413 lines)

**Role:** Seven-phase expert system recommending a technology train and pretreatment sequence based on feed water quality.

**Class:** `ProcessRecommendationEngine`

| Phase | Method | Function |
|---|---|---|
| 0 | `_phase_0_confidence()` | Fills defaults for missing inputs; deducts confidence score points |
| 1 | `_phase_1_source_type()` | Classifies source (SEAWATER, BRACKISH_GW, SURFACE, LOW_TDS, WASTEWATER). HALT if BOD/COD too high. |
| 2 | `_phase_2_fouling()` | Recommends pretreatment based on SDI, turbidity, TOC, iron, manganese, Cl2, oil/grease |
| 3 | `_phase_3_primary_process()` | Assigns primary technology (BWRO, SWRO, NF, EDI) based on TDS and source |
| 4 | `_phase_4_scaling()` | Runs PHREEQC at system recovery CF to check scaling risks; adjusts recommended recovery |
| 5 | `_phase_5_permeate_quality()` | Checks if a second RO pass is needed for boron removal or ultra-pure water targets |
| 6 | `_phase_6_nf_refinement()` | Refines NF suitability based on divalent ion content |
| 7 | `_phase_7_final_assembly()` | Combines all decisions into the final recommendation object |

**Confidence scoring:** Starts at 100. Each missing input field deducts points. Final level: HIGH (>=80), MEDIUM (>=55), LOW (<55).

---

### 5.7 `membrane_recommender.py` — Membrane Selection Engine

**Location:** `backend/membrane_recommender.py` (~238 lines)

**Role:** Iterates over all Permionics membranes, simulates each one using `SystemEngine.calculate_system()`, and scores them on four weighted criteria.

**Class:** `MembraneRecommender`

**Scoring weights:**
```
W_REJECTION = 30   # Permeate TDS vs target TDS
W_HYDRAULIC  = 20  # Feed pressure headroom vs max_pressure
W_ENERGY     = 30  # Specific energy consumption (kWh/m3)
W_ENVELOPE   = 20  # Operating within flux/flow design envelope
```

**Membrane filtering logic:**
- NF trains: filters to `type == "NF"` membranes.
- RO trains: filters Permionics BWRO/SWRO based on feed TDS:
  - TDS > 20,000 mg/L -> SWRO only
  - TDS 15,000–20,000 mg/L -> BWRO and SWRO
  - TDS < 15,000 mg/L -> BWRO only
- Disqualified if simulation throws an exception or if permeate TDS > target.
- Best membrane = highest non-disqualified total score.

---

### 5.8 `conditioning.py` — Interstage pH Conditioning

**Location:** `backend/conditioning.py` (~58 lines)

**Role:** Applied between Pass 1 and Pass 2 in a two-pass RO system. Adjusts pH and ion concentrations to simulate NaOH, H2SO4, or HCl dosing, and optionally simulates CO2 degassing.

| Function | Purpose |
|---|---|
| `compute_chemical_dose(ions, target_ph, chemical)` | Estimates chemical dose (mg/L) as `delta_pH x 2.5` (linear approximation) |
| `apply_conditioning(p1_permeate_ions, cond_cfg)` | Applies CO2 degassing and pH adjustment. Returns `(conditioned_ions, dose_mg_l, final_ph)` |

**Chemicals supported:** `NaOH` (raises Na+), `H2SO4` (raises SO4 2-), `HCl` (raises Cl-).

---

### 5.9 `physics_aging_engine.py` — Multi-Year Projection Engine

**Location:** `backend/physics_aging_engine.py` (~1,702 lines)

**Role:** The primary membrane aging model. Implements five physics-based fouling sub-models and CIP kinetics. Produces monthly and annual snapshots of NPF, NSP, SEC, permeate TDS, and feed pressure.

**Class:** `PhysicsAgingEngine`

**Entry point:** `run_physics_projection(baseline_ro_result, feed_ions, temp_c, ph, membrane_model, stages, vessels_per_stage, elements_per_vessel, target_recovery_pct, feed_flow_m3h, n_years, feed_quality, cip_config, antiscalant_dosed, recycle_feed_ions, bulk_si)`

**Key constants:**
```python
NZ    = 10       # Axial segments per element (spatial resolution)
DT_H  = 730.0    # Timestep = 1 month in hours
R_GAS = 8.314    # J/(mol K)
```

**Physics parameters** (`DEFAULT_PHYSICS_PARAMS` dict, ~30 constants): Covers cake filtration (Kd, K_rem, alpha0), biofouling (mu_max, Ks, bd), scaling (gamma_sl, theta_contact, kg_calcite), NOM (qmax, KL, kads), and compaction (Em, tau_c, eta_v). All are overridable via the `model_params` field in the API input.

---

### 5.10 `aging_engine.py` — Legacy Aging Engine (Deprecated)

**Location:** `backend/aging_engine.py` (~1,027 lines)

**Status: DEPRECATED.** Both `/api/simulate-aging` and `/api/calculate-system-physics` now route exclusively through `PhysicsAgingEngine`. The legacy engine is retained only for historical reference.

**Do not use this module for any new development.** All fouling model improvements must go into `physics_aging_engine.py`.

---

### 5.11 `report_generator.py` — PDF Report Generator

**Location:** `backend/report_generator.py` (~2,000+ lines)

**Role:** Generates a WAVE-style formatted `.docx` calculation report from the system result dictionary. `server.py` then converts it to PDF and adds a diagonal "PERMIONICS" watermark using PyMuPDF.

**Class:** `ReportGenerator`

**Primary method:** `generate_calculation_report(result_dict, output_path)`

**Report sections generated (in order):**
1. Cover page — project details, Permionics logo, date
2. Feed water analysis table — all ions + physical parameters
3. Scaling indices — feed SI, concentrate SI, PHREEQC results
4. System configuration summary — technology train, membrane, stages, vessels
5. UF performance table (if UF in train)
6. RO/NF performance — element-by-element flux, recovery, CP, NDP
7. Concentrate water quality
8. Booster pump sizing table
9. Hydraulic warnings table
10. NF-specific analysis (if NF train)
11. Economic analysis — CAPEX, OPEX, cost per kL
12. Membrane aging / performance projection (if physics_results provided)
13. Process Flow Diagram (if PFD PNG provided)

---

### 5.12 `run_app.py` — Application Entry Point

**Location:** `backend/run_app.py` (41 lines)

Imports the FastAPI `app` from `server.py`, mounts `ui_ux_design/` as static files, and starts Uvicorn. Handles both frozen (PyInstaller `.exe`) and script execution modes.

```python
ui_dir = os.path.join(os.path.dirname(base_dir), "ui_ux_design")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
uvicorn.run(app, host="0.0.0.0", port=port)
```

---

## 6. API Endpoint Reference

All `/api/` endpoints require **HTTP Basic Authentication**.

**Default credentials:**
- Username: `pace_permionics` (override via `API_USERNAME` env var)
- Password: `satyaraj_permionics@2026` (override via `API_PASSWORD` env var)

---

### `GET /`
Redirect to frontend `index.html`. Auth not required.

---

### `POST /api/verify-auth`
Verify credentials. Request: empty body. Response: `{"status": "success"}`.

---

### `POST /api/calculate-scaling`
Run PHREEQC feed water scaling analysis only.

**Request:** `FeedWaterData` (all ions in mg/L + temperature + pH)

**Response:**
```json
{
  "gypsum_si": -0.45,     "calcite_si": 0.23,    "aragonite_si": 0.09,
  "barite_si": -1.20,     "lsi": 0.23,           "celestite_si": -0.80,
  "fluorite_si": -2.10,   "anhydrite_si": -0.60, "silica_si": -0.90,
  "iron_si": 1.30,        "aluminium_si": -0.10, "manganese_si": -0.50,
  "calcium_phosphate_si": 5.20
}
```

---

### `POST /api/auto-balance`
Compute Charge Balance Error (CBE) and auto-balance by injecting Na+ or Cl-.

**Response:**
```json
{
  "status": "ADJUSTED",
  "cbe_meq": 0.42,
  "cbe_pct": 3.1,
  "sum_cations_meq": 12.5,
  "sum_anions_meq": 12.08,
  "injected_ion": "Cl",
  "injected_amount_mg_l": 14.9,
  "message": "Cl- auto-added: 14.90 mg/L to balance charge."
}
```

---

### `POST /api/process-recommendation`
Seven-phase process recommendation engine. Returns primary config, pretreatment flags, scaling risks, and confidence score.

---

### `POST /api/calculate-system`
**Main calculation endpoint.** Full system simulation.

**Request:** `SystemCalcInput`

**Response includes:**
- `technology_train`, `feed_water_used`
- `uf_results` (null if no UF)
- `ro_results` -> `{summary, stages, elements, booster_pumps, warnings}`
- `economics` (if `economic_params` provided)
- `concentrate_ph`, `concentrate_si`, `feed_si` (PHREEQC)
- For 2P-RO: also `pass1_results`, `pass2_results`, `system_summary`, `conditioning`, `recycle`

---

### `POST /api/auto-select-membrane`
Quick membrane auto-select using `MembraneRecommender`.
**Response:** `{"best_membrane": "HPA-RO-8040", "max_recovery": 0.75}`

---

### `GET /api/membranes`
List all membranes and UF modules.
**Response:** `{"ro_membranes": [...], "uf_modules": [...]}`

---

### `POST /api/recommend-membrane`
Full multi-criteria membrane recommendation with scores, criteria breakdown, and justification text.

---

### `POST /api/generate-calculation-report`
Generate and download a PDF calculation report.
**Response:** Binary PDF file stream (with PERMIONICS watermark). Filename: `PACE_Calculation_Report.pdf`.

---

### `POST /api/simulate-aging`
Physics-based membrane aging simulation (for the "Membrane Aging" tab).

**Request:** `AgingSimInput` (system config + aging config + feed history)

**Response:**
```json
{
  "aging_profile": [...],          // Monthly NPF, NSP, pressure
  "cip_events": [...],             // Month and type of each CIP
  "end_of_life_month": 54,         // Month when NPF < 0.80
  "dominant_mechanism": "Biofouling",
  "mechanism_totals": {...},
  "element_autopsy": {...},
  "annual_snapshots": [...]
}
```

---

### `POST /api/calculate-system-physics`
Physics-based multi-year projection for a specific `projection_year`.

**Request:** `PhysicsCalcInput`

**Response:** Full system result for the selected year merged with `physics_results` and annual snapshots.

> **Architecture note:** Both `/api/simulate-aging` and `/api/calculate-system-physics` call the same `_run_projection_core()` internal function. This guarantees both tabs **always agree** on results for the same scenario.

---

## 7. Data Models (Pydantic Schemas)

### `FeedWaterData` — All concentrations in mg/L

| Field | Type | Default | Description |
|---|---|---|---|
| `temperature` | float | 25.0 | Feed temperature (degC) |
| `ph` | float | 7.0 | Feed pH |
| `calcium` | float | 0.0 | Ca2+ (mg/L) |
| `magnesium` | float | 0.0 | Mg2+ |
| `sodium` | float | 0.0 | Na+ |
| `chloride` | float | 0.0 | Cl- |
| `sulfate` | float | 0.0 | SO4 2- |
| `bicarbonate` | float | 0.0 | HCO3- (as HCO3) |
| `strontium` | float | 0.0 | Sr2+ |
| `fluoride` | float | 0.0 | F- |
| `silica` | float | 0.0 | SiO2 |
| `barium` | float | 0.0 | Ba2+ |
| `potassium` | float | 0.0 | K+ |
| `ammonium` | float | 0.0 | NH4+ |
| `carbonate` | float | 0.0 | CO3 2- |
| `nitrate` | float | 0.0 | NO3- |
| `aluminium` | float | 0.0 | Al3+ |
| `iron` | float | 0.0 | Fe (total) |
| `manganese` | float | 0.0 | Mn |
| `phosphate` | float | 0.0 | PO4 3- |
| `boron` | float | 0.0 | B |
| `tss` | float (opt) | 0.0 | Total suspended solids (mg/L) |
| `turbidity` | float (opt) | 0.0 | Turbidity (NTU) |
| `tds` | float (opt) | 0.0 | Total dissolved solids (mg/L) |

### `SystemCalcInput`

| Field | Type | Default | Description |
|---|---|---|---|
| `technology_train` | str | — | `"RO"`, `"UF+RO"`, `"NF"`, `"UF+NF"`, `"2P-RO"`, `"UF+2P-RO"` |
| `feed_water` | dict | — | FeedWaterData fields |
| `target_flow_m3h` | float | — | Required system product flow (m3/h) |
| `target_recovery_pct` | float | — | Target system recovery (%) |
| `target_tds` | float (opt) | 50.0 | Target permeate TDS (mg/L) |
| `ro_membrane` | str | — | Membrane model ID |
| `uf_module` | str (opt) | None | UF module ID (required if UF in train) |
| `stages` | int | — | Number of RO/NF stages |
| `vessels_per_stage` | List[int] | — | e.g. `[4, 2]` for 2-stage |
| `elements_per_vessel` | int | — | Typically 6 |
| `economic_params` | EconomicParams (opt) | None | Cost parameters |
| `recycle_enabled` | bool (opt) | False | Enable concentrate recycle |
| `recycle_ratio` | float (opt) | 0.0 | Fraction of concentrate recycled (0-1) |
| `pass1` | PassConfig (opt) | None | Pass 1 config (for 2P-RO) |
| `pass2` | PassConfig (opt) | None | Pass 2 config (for 2P-RO) |
| `conditioning` | ConditioningConfig (opt) | None | Interstage conditioning (for 2P-RO) |
| `recycle` | RecycleConfig (opt) | None | Recycle config (for 2P-RO with recycle) |

### `EconomicParams`

| Field | Default | Description |
|---|---|---|
| `electricity_tariff` | 7.50 | Rs/kWh |
| `membrane_cost` | 26,880 | Rs/element (RO BWRO default) |
| `vessel_cost` | 48,000 | Rs/pressure vessel |
| `pump_cost_kw` | 96,000 | Rs/kW installed pump capacity |
| `ic_factor` | 0.15 | Installation & commissioning factor (15%) |
| `contingency_factor` | 0.10 | Contingency factor (10%) |
| `plant_availability` | 0.90 | Fraction of 8760 h/yr the plant operates |
| `membrane_lifetime` | 5.0 | RO membrane replacement interval (years) |
| `uf_membrane_lifetime` | 7.0 | UF module replacement interval (years) |
| `discount_rate` | 0.10 | Discount rate for CRF |
| `project_life` | 20.0 | Project life for LCOE (years) |

### `PhysicsCalcInput`
Extends `SystemCalcInput` with:

| Field | Default | Description |
|---|---|---|
| `projection_year` | 0 | Which year to display (0 = Year 0 / fresh) |
| `n_years` | 5 | Total projection horizon |
| `feed_quality.sdi15` | 3.0 | SDI-15 index |
| `feed_quality.toc_mg_l` | 2.0 | TOC (mg/L) |
| `feed_quality.cl2_residual_mg_l` | 0.0 | Free Cl2 after SBS dosing (mg/L) |
| `cip_config.interval_months` | 0 | 0 = condition-triggered; >0 = fixed schedule |
| `antiscalant_dosed` | True | Whether antiscalant is dosed |

---

## 8. Technology Trains — Data Flow

### 8.1 RO (Single-Pass)

```
Feed Water
    |
    v (bisection: find P_feed for target recovery)
ROEngine.simulate_system(stages, vessels, elements, membrane)
    |
    v
ro_results {summary, stages, elements, booster_pumps, warnings}
    |
    v (optional)
Economic calculation
    |
    v
PHREEQC concentrate SI
```

---

### 8.2 UF+RO

```
Feed Water
    |
    v
UFEngine.simulate_uf(gross_flow, module, design_flux)
    |-- uf_results (modules count, net_product_m3h, TMPs, warnings)
    |
    v net_product_m3h (unchanged ion composition)
    |
    v (bisection: find P_feed)
ROEngine.simulate_system(...)
    |
    v
Combined result: uf_results + ro_results
```

**Key:** UF does NOT remove dissolved salts. Feed ions to RO are identical to raw feed ions.

---

### 8.3 2P-RO (Two-Pass RO)

```
Feed Water
    |
    v [Bisection: P1_feed -> target Pass1 recovery]
ROEngine.simulate_system(pass1 config)
    |
    v Pass 1 permeate ions
    |
    v conditioning.apply_conditioning(cond_cfg)  [optional pH adjust + CO2 degas]
    |
    v [Auto-size Pass 2 vessels if user count insufficient]
    |
    v [Bisection: P2_feed -> target Pass2 recovery]
ROEngine.simulate_system(pass2 config)
    |
    v pass1_results + pass2_results + system_summary
    |
    v [Optional: loop for P2 concentrate recycle back to P1, converge]
```

**Pass 2 auto-sizing formula:**
```
min_elements = ceil(p1_perm_flow * p2_target_rec / (elem_area_m2 * 20/1000))
```
(20 LMH is the reference design flux for Pass 2 sizing.)

---

### 8.4 UF+2P-RO

Identical to 2P-RO except the first step is a UF stage:
- UF net product feeds Pass 1.
- Otherwise the 2P-RO flow is unchanged.

---

### 8.5 NF and UF+NF

Uses `ROEngine.simulate_system()` with an NF membrane. Additional steps in `SystemEngine.calculate_system()` when `"NF" in train`:

1. Feed quality pre-checks (TDS, SDI, Fe, Mn, Cl2, TOC, turbidity, pH) with CRITICAL/WARNING severities.
2. Pretreatment recommendations (cartridge filter always; iron removal, dechlorination, pH correction as needed).
3. Post-solve concentrate scaling indices via Davies equation (CaSO4, BaSO4, SrSO4, CaF2, SiO2, CaCO3).
4. Hard stop warning if P_feed > 41 bar (code: `NF-W-HYD-10 CRITICAL`).
5. Result extended with `nf_analysis` key.

**NF-specific physics:**
- Per-ion solute permeabilities `nf_ps` (from membrane database) used in Spiegler-Kedem instead of the single `B` parameter.
- Donnan electroneutrality correction: Cl- concentration adjusted after transport equations to satisfy cation-anion balance in permeate.
- Membrane-specific `E_Aw_over_R` activation energy used in TCF.

---

### 8.6 Concentrate Recycle Loop

Triggered when `recycle_enabled = True` and `recycle_ratio > 0`:

```
Iteration i:
  Q_blend = Q_fresh + Q_r_prev
  C_blend = (C_fresh * Q_fresh + C_r_prev * Q_r_prev) / Q_blend

  calculate_system(Q_blend, C_blend)
    -> ro_result -> Q_perm, Q_conc, C_conc

  Q_r_new = recycle_ratio * Q_conc
  C_r_new = C_conc (last element concentrate ions)

  Convergence: |Q_perm_new - Q_perm_prev| / Q_perm_prev < 0.002 (0.2%)
  Max iterations: 15

Output includes:
  effective_system_recovery = Q_perm / Q_fresh
  blended_feed_ions         = C_blend  (used by physics engine)
```

---

## 9. Key Calculation Algorithms

### 9.1 Osmotic Pressure (van't Hoff)

```
pi = phi * C_total_mol * R * T

Where:
  phi            = TDS-dependent osmotic coefficient (0.90 to 1.0)
  C_total_mol    = sum of all ion molar concentrations (mol/L)
  R              = 0.08314 L.bar/(mol.K)
  T              = temperature in Kelvin

phi lookup:
  TDS >= 35,000  -> phi = 0.90
  10,000-35,000  -> linear 0.93->0.90
  1,000-10,000   -> phi = 0.93
  500-1,000      -> phi = 0.95
  100-500        -> linear 0.98->0.95
  < 100          -> phi = 1.0
```

---

### 9.2 Temperature Correction Factor (TCF)

```
TCF(T) = exp( (E_Aw/R) * (1/T_ref - 1/T) )

For NF membranes:
  E_Aw/R is read from the membrane database entry (field: E_Aw_over_R)

For RO membranes (legacy formula):
  U = 2640  if T <= 25 degC
  U = 3020  if T >  25 degC
  T_ref = 298.15 K (25 degC)
```

---

### 9.3 Concentration Polarization (CP / Beta)

Film theory with Schock-Miquel Sherwood correlation:

```
Re  = rho * v_feed * d_h / mu
Sc  = mu / (rho * D_AB)
Sh  = 0.04 * Re^0.75 * Sc^0.33

k   = Sh * D_AB / d_h          (mass transfer coefficient, m/s)
beta = exp(J_v / k)             (CP factor = Cm/Cb)

Where:
  d_h = 2 * t_spacer            (hydraulic diameter from spacer thickness)
  D_AB = ion-weighted diffusivity corrected to temperature T
  J_v = water flux (m/s)
  beta is capped at beta_cap (1.25 for Pass 1, 1.20 for Pass 2)
```

---

### 9.4 Spiegler-Kedem Solute Transport

True rejection from reflection coefficient and solute permeability:

```
R_true = 1 - (1 - sigma) / (1 - sigma * exp(-Jv*(1-sigma)/Ps))

Observed permeate concentration (self-consistent with CP):
  Cp = Cb * beta * (1 - R_true) / (R_true + beta*(1 - R_true))

For NF membranes:
  Ps is taken from the per-ion nf_ps dict in the membrane database.
For RO membranes:
  Ps = B * (1 - sigma) / 0.01  (derived from B parameter)

Donnan Correction (NF only):
  After computing all permeate ions, adjust Cl- so that:
  sum(cation meq) = sum(anion meq including Cl-)
  This enforces electroneutrality in the NF permeate.
```

---

### 9.5 Pressure Drop (Schock-Miquel)

```
lambda = 6.23 * Re^(-0.3)        (friction factor)
dP_elem = lambda * (L/d_h) * (rho * v^2 / 2)

Capped at 1.5 bar/element minimum, 0.001 bar/element minimum.
```

---

### 9.6 Interstage Booster Pump Sizing

```
pi_conc       = osmotic pressure of stage concentrate
target_NDP    = average NDP of the preceding stage (min 0.5 bar)
P_required    = pi_conc + target_NDP + 0.5    (0.5 bar back-pressure)
P_available   = stage_exit_pressure - 0.5     (0.5 bar piping loss)
boost_DP      = max(0, P_required - P_available)

P_booster_kW  = (Q_conc_m3h * boost_DP_bar) / (36 * 0.75)
                                          (pump efficiency = 0.75)
```

---

### 9.7 Feed Pressure Solver (Bisection)

25-iteration bisection loop in `SystemEngine.calculate_system()`:
- Lower bound: `max(1.0, est_osmotic - 5.0)`
- Upper bound: `max(120.0, est_osmotic + 60.0)`
- Convergence tolerance: `|rec - target| < 0.005` (0.5%)

---

### 9.8 Charge Balance Error (CBE) & Auto-Balance

```
CBE% = (sum_cation_meq - sum_anion_meq) / (sum_cation_meq + sum_anion_meq) * 100

If |CBE%| > 2%:
  CBE > 0  (excess cations)  -> inject Cl-:
      Cl_final += CBE_meq * MW_Cl   (MW_Cl = 35.45)
  CBE < 0  (excess anions)   -> inject Na+:
      Na_final += |CBE_meq| * MW_Na (MW_Na = 22.99)
```

---

### 9.9 PHREEQC Scaling Indices (SI)

```
SI = log10(IAP / Ksp)

  IAP = Ion Activity Product (accounts for activity coefficients)
  Ksp = Solubility product constant

SI > 0  =>  supersaturated  => scaling risk
SI < 0  =>  undersaturated  => no risk

Minerals evaluated:
  Calcite, Aragonite, Dolomite, Gypsum, Anhydrite,
  Barite, Celestite, Fluorite, SiO2(a)
```

Concentrate solution is built from engine concentrate ion concentrations. pH is estimated from the HCO3 concentration factor relative to feed:
```
est_conc_ph = feed_ph + log10(conc_HCO3 / feed_HCO3)
```

---

### 9.10 NF Concentrate Scaling (Davies)

Davies ionic-strength correction for activity coefficients:

```
log(gamma_z) = -A * z^2 * (sqrt(I)/(1+sqrt(I)) - 0.3*I)
               A ~ 0.509 at 25 degC

Ionic strength I = 0.5 * sum(ci * zi^2)   [mol/L]

Scalants:
  CaSO4   Ksp = 4.93e-5
  BaSO4   Ksp = 1.08e-10
  SrSO4   Ksp = 3.44e-7
  CaF2    Ksp = 3.45e-11
  SiO2    Saturation% vs 100 mg/L solubility at 25 degC
  CaCO3   LSI (Langelier Saturation Index)
```

---

## 10. Physics Aging Model Details

Spec reference: PACE-FEAT-MPP-002 Rev-A
Engine: `physics_aging_engine.py`, class `PhysicsAgingEngine`

The engine simulates month-by-month fouling for `n_years * 12` timesteps of 730 hours each.

---

### 10.1 Sub-model I — Cake / Colloid Filtration (RK4)

Cake resistance buildup solved with 4th-order Runge-Kutta (RK4) ODE integration:

```
dRc/dt = Kd * Jv * Cb - Krem * tau_w * Rc

  Kd    = deposition rate constant
  Krem  = shear removal rate constant
  tau_w = wall shear stress (Pa)
  Cb    = bulk particle concentration (derived from SDI15)

Compressible cake correction:
  alpha_cake(TMP) = alpha0 * (TMP / TMP_ref)^sc
```

---

### 10.2 Sub-model II — Biofouling (Monod)

Biofilm thickness growth with Monod kinetics:

```
dLb/dt = mu_max * (BDOC / (Ks + BDOC)) * exp(k_muT*(T-Tref)) * Lb - bd * Lb

  BDOC  = biodegradable dissolved organic carbon (from TOC)
  mu_max = maximum specific growth rate (d-1)
  Ks    = half-saturation constant
  bd    = decay/detachment coefficient

Biofilm EPS hydraulic resistance (Happel-Brenner model):
  R_bf = mu * Lb / kappa_EPS
  kappa_EPS = Kozeny-Carman permeability of EPS matrix
```

---

### 10.3 Sub-model III — Inorganic Scaling (CNT)

Classical Nucleation Theory governs induction time:

```
J_nuc = A_ind * exp(-16*pi*gamma_sl^3*Vm^2 / (3*(kB*T)^3 * (ln S)^2) * f(theta))

  S              = supersaturation ratio (from bulk SI)
  gamma_sl       = solid-liquid interfacial energy
  f(theta)       = geometric factor from contact angle

After induction, crystal growth:
  dm_scale/dt = kg * A_crystal * (S-1)^n

Scale resistance:
  R_scale = alpha_scale * m_scale

Antiscalant effect:
  Shifts effective SI threshold by delta_si_antiscalant
  (e.g., +0.5 for Calcite means scaling only starts at SI > 0.5)
```

---

### 10.4 Sub-model IV — NOM Adsorption (Langmuir)

Reversible Langmuir adsorption + irreversible intermediate blocking:

```
dq/dt = kads * (qmax * KL*C_NOM/(1+KL*C_NOM) - q) - kdes * q

Intermediate blocking (pore constriction):
  d_theta_NOM/dt = kIB * Jv * C_NOM * (1 - theta_NOM)

NOM resistance:
  R_NOM = r_NOM * q + R_block * theta_NOM
```

---

### 10.5 Sub-model V — Membrane Compaction (Kelvin-Voigt)

Viscoelastic creep under sustained pressure:

```
eps_c(t) = (f_stress * P_feed / Em) * (1 - exp(-t/tau_c))

  Em    = elastic modulus of the polyamide active layer
  tau_c = retardation time constant
  f_stress = stress concentration factor

Compaction decreases effective membrane thickness, which
increases the water permeability A over time (irreversible
once pressure is sustained beyond the elastic limit).
```

---

### 10.6 Salt Permeability Degradation

Arrhenius chemical attack on the polyamide layer:

```
B_eff(t) = B0 * exp(k_B_chem * t) * exp(Ea_B/R * (1/Tref - 1/T))

  k_B_chem = 0.03 /yr  (baseline Cl2/pH-driven degradation)
  Ea_B     = 60,000 J/mol

Irreversible B accumulation is tracked as b_irr in annual snapshots.
```

---

### 10.7 CIP Kinetics

**Acid CIP** (Calcite/carbonate scale dissolution):
```
dm_scale/dt|CIP = -kd_acid * A_crystal * [H+] * exp(-Ea_dis/RT)
```

**Alkaline CIP** (biofilm/NOM removal):
```
dLb/dt|CIP = -kd_bio * [OH-]
```

**CIP trigger (dynamic mode, `cip_interval_months = 0`):**
```
CIP fires when ANY of:
  NPF < 0.85   (flux decline > 15%)
  P_ratio > 1.35  (feed pressure risen > 35% above baseline)
  FRI > 0.60   (fouling resistance index > 0.60)
```

---

### 10.8 ASTM D4516-19a Normalisation

**Normalised Permeate Flow (NPF):**
```
NPF(t) = (Qp(t) / Qp0) * (NDP0 / NDP(t))
```

**Normalised Salt Passage (NSP):**
```
NSP(t) = SP(t) / SP(0)
SP = Cp / Cf   (permeate concentration / feed concentration)
```

**Net Driving Pressure (NDP):**
```
NDP(t) = P_feed(t) - dP_friction(t)/2 - P_back - pi_m(t) + pi_p(t)
```

Year 0 is always forced to: NPF = 1.0, NSP = 1.0 (ASTM baseline).

---

## 11. Economic Analysis Model

Economics are computed inside `SystemEngine.calculate_system()` when `economic_params` is provided.

### CAPEX

```
Equipment subtotal:
  C_membranes  = n_elements * unit_membrane_cost
  C_vessels    = n_vessels * vessel_cost
  C_HP_pump    = hp_pump_kW * pump_cost_kw
  C_BP_pump    = booster_pump_kW * pump_cost_kw
  C_UF_modules = n_uf_modules * uf_module_cost   (if UF in train)
  C_UF_pumps   = UF_pump_kW * pump_cost_kw       (if UF in train)

CAPEX = (Equipment Subtotal) * (1 + ic_factor) * (1 + contingency_factor)
```

Default multipliers: ic_factor = 15%, contingency_factor = 10%

### Membrane Unit Costs (defaults)
- BWRO: Rs 26,880 / element
- SWRO: Rs 30,240 / element
- NF:   Rs 19,200 / element

### OPEX (per annum)

```
hours_pa         = plant_availability * 8760

Energy cost:
  E_energy = (HP_pump_kW + BP_pump_kW + UF_pump_kW) * hours_pa * tariff

RO membrane replacement:
  E_RO_mem = CAPEX_membranes / membrane_lifetime_years

UF membrane replacement:
  E_UF_mem = CAPEX_UF / uf_membrane_lifetime_years

UF CEB chemicals (if UF):
  E_CEB = 7 g/m3_net_permeate * q_net_pa * Rs 30/kg

OPEX_pa = E_energy + E_RO_mem + E_UF_mem + E_CEB
```

### Capital Recovery Factor (CRF)

```
CRF = r*(1+r)^n / ((1+r)^n - 1)
  r = discount_rate
  n = project_life (years)
```

### Cost per kL

```
Cost_per_kL = (CRF * CAPEX + OPEX_pa) / (Q_perm * hours_pa)
```

---

## 12. Membrane Database Schema

### 12.1 RO/NF Membrane Fields

```python
{
  # Identity
  "type":                 str,    # "BWRO", "SWRO", or "NF"
  "manufacturer":         str,    # e.g. "Permionics"

  # Physical geometry
  "active_area_m2":       float,  # Active membrane area per element (m2)
  "length_m":             float,  # Element length (m), typically 1.016
  "diameter_m":           float,  # Element diameter (m), typically 0.201
  "feed_spacer_mil":      int,    # Feed channel spacer thickness (mil)

  # Transport parameters
  "permeability_A":       float,  # Water permeability A (LMH/bar) at 25 degC
  "permeability_B":       float,  # Salt permeability B (m/s) at 25 degC
  "sigma": {                      # Spiegler-Kedem reflection coefficients (0-1)
    "Ca": float, "Mg": float, "Na": float, "K": float,
    "Cl": float, "SO4": float, "HCO3": float, "Ba": float,
    "Sr": float, "F": float, "SiO2": float, "B": float,
    "NO3": float, "PO4": float, "NH4": float
  },

  # NF-specific (only for NF membranes)
  "nf_ps": {              # Per-ion Ps in m/s (higher = less rejection)
    "Ca": float, "SO4": float, "Cl": float, "Na": float, ...
  },
  "E_Aw_over_R":          float,  # Activation energy for TCF (K)

  # Operating limits
  "max_pressure_bar":     float,  # Maximum operating pressure
  "max_feed_flow_m3h":    float,  # Max feed flow per vessel
  "min_conc_flow_m3h":    float,  # Min concentrate flow (anti-telescoping)
  "max_recovery_pct":     float,  # Max element recovery (typically 15%)
  "max_temp_c":           float,  # Maximum operating temperature
  "ph_range":             [float, float],  # Operating pH [min, max]
  "cip_ph_range":         [float, float],  # CIP pH [min, max]
  "max_turbidity_ntu":    float,
  "max_sdi_15":           float,  # Maximum SDI-15
  "max_chlorine_mgL":     float,  # Max free Cl2 tolerance (mg/L)

  # Rejection specifications
  "nominal_rejection":    float,  # Nominal salt rejection (0-1)
  "min_rejection":        float,  # Minimum guaranteed rejection

  # Flags
  "flags":                list,   # e.g. ["LF"] = low-fouling, ["FR"] = fouling-resistant

  # Source-specific design flux guidelines
  "design_flux_guidelines": {
    "well_water":               {"sdi_max": 3, "flux_min_lmh": 22.1, "flux_max_lmh": 28.9},
    "surface_water_sdi5":       {"sdi_max": 5, "flux_min_lmh": 20.4, "flux_max_lmh": 27.2},
    "wastewater_conventional":  {"sdi_max": 5, "flux_min_lmh": 13.6, "flux_max_lmh": 20.4},
    "seawater_open_intake":     {"sdi_max": 5, "flux_min_lmh": 11.9, "flux_max_lmh": 17.0},
    "ro_permeate":              {"sdi_max": 1, "flux_min_lmh": 35.7, "flux_max_lmh": 51.0},
    # ... more source types
  },

  # Scaling limits
  "saturation_limits": {
    "LSI":        float,  # Max Langelier SI (typically 1.5)
    "SDSI":       float,  # Max Stiff-Davis SI (typically 0.5)
    "CaSO4_pct":  int,    # % of CaSO4 saturation limit (typically 230%)
    "SrSO4_pct":  int,    # % of SrSO4 saturation limit (typically 800%)
    "BaSO4_pct":  int,    # % of BaSO4 saturation limit (typically 6000%)
    "SiO2_pct":   int,    # % of SiO2 saturation limit (typically 100%)
  },
}
```

### 12.2 UF Module Fields

```python
{
  "type":                        str,    # "UF"
  "manufacturer":                str,    # e.g. "Permionics"
  "membrane_area_m2":            float,  # Total filtration area per module (m2)
  "fiber_id_mm":                 float,  # Hollow fiber inner diameter (mm)
  "max_filtration_flux_lmh":     float,  # Maximum operating flux (LMH)
  "design_flux_lmh":             float,  # Recommended design flux (LMH)
  "clean_tmp_max_bar":           float,  # Max TMP for clean membrane (bar)
  "fouled_tmp_max_bar":          float,  # Max TMP for fouled membrane (bar)
  "max_tmp_bar":                 float,  # Absolute maximum TMP (bar)
  "backwash_flux_lmh":           float,  # Backwash flux (LMH)
  "backwash_duration_s":         int,    # Backwash duration (seconds)
  "air_scour_flow_m3h":          float,  # Air scour flow (m3/h)
  "min_forward_flush_m3h":       float,  # Minimum forward flush flow (m3/h)
  "permeability_Lp20":           float,  # Permeability at 20 degC (LMH/bar)
  "unit_cost_inr":               float,  # Cost per module (Rs)
  "feed_pump_kw_per_module":     float,  # Feed pump power per module (kW)
  "backwash_pump_kw_per_module": float,  # Backwash pump power per module (kW)
}
```

---

## 13. Authentication & Security

The `BasicAuthASGIMiddleware` class in `server.py` intercepts all ASGI calls:

```python
class BasicAuthASGIMiddleware:
    """
    Protects /api/* routes with HTTP Basic Authentication.
    Passes through:
      - Non-HTTP scopes (WebSocket, lifespan)
      - OPTIONS preflight requests
      - Paths NOT starting with /api/
    """
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": ...
        if scope["path"].startswith("/api/"):
            # Decode Authorization: Basic <base64> header
            # Compare to API_USERNAME / API_PASSWORD env vars
            # Return 401 WWW-Authenticate if mismatch
        await self.app(scope, receive, send)
```

**Environment variables for credentials:**
```bash
API_USERNAME=pace_permionics
API_PASSWORD=satyaraj_permionics@2026
```

CORS is configured to allow all origins (since authentication is via Basic Auth, not session/CSRF):
```python
app.add_middleware(CORSMiddleware, allow_origin_regex=".*", allow_credentials=True, ...)
```

---

## 14. Extension Guide — How to Add New Features

> **Rule before any change:** Understand which module owns the feature you are changing. The layer boundaries are strict:
> - Transport physics -> `calc_engine.py` or `uf_engine.py`
> - System orchestration -> `system_engine.py`
> - Data/catalog -> `membrane_database.py`
> - API surface -> `server.py`
> - Aging projections -> `physics_aging_engine.py`
> - Reports -> `report_generator.py`

---

### 14.1 Adding a New RO/NF Membrane

**File to modify:** `backend/membrane_database.py` ONLY.

**Step 1 — Add the entry to `MembraneDatabase.RO_MEMBRANES`:**

Copy the closest existing membrane as a template, then update all values from the manufacturer datasheet:

```python
"MY-NEW-MEMBRANE-8040": {
    "type": "BWRO",             # or "SWRO" or "NF"
    "manufacturer": "Permionics",
    "active_area_m2": 37.2,
    "permeability_A": 3.0,      # LMH/bar  -- see calculation below
    "permeability_B": 4.0e-8,   # m/s      -- see calculation below
    "feed_spacer_mil": 34,
    "max_pressure_bar": 41.4,
    "max_feed_flow_m3h": 16.0,
    "min_conc_flow_m3h": 4.5,
    "max_recovery_pct": 15.0,
    "length_m": 1.016,
    "diameter_m": 0.201,
    "nominal_rejection": 0.997,
    "min_rejection": 0.996,
    "flags": [],                # ["LF"] for low-fouling, ["FR"] for fouling-resistant
    "max_temp_c": 45.0,
    "ph_range": [2.0, 11.0],
    "cip_ph_range": [1.0, 13.0],
    "max_turbidity_ntu": 1.0,
    "max_sdi_15": 5.0,
    "max_chlorine_mgL": 0.1,
    "design_flux_guidelines": {
        # Copy from an existing BWRO membrane for the same application
        "well_water": {"sdi_max": 3, "flux_min_lmh": 22.1, "flux_max_lmh": 28.9},
        "surface_water_sdi5": {"sdi_max": 5, "flux_min_lmh": 20.4, "flux_max_lmh": 27.2},
        ...
    },
    "saturation_limits": {
        "LSI": 1.5, "SDSI": 0.5,
        "CaSO4_pct": 230, "SrSO4_pct": 800,
        "BaSO4_pct": 6000, "SiO2_pct": 100,
    },
    "sigma": {
        # From manufacturer datasheet ion-rejection data.
        # Sigma = rejection coefficient in Spiegler-Kedem (0=no rejection, 1=perfect)
        # Typical BWRO starting point:
        "Ca": 0.997, "Mg": 0.997, "Na": 0.988, "K": 0.983,
        "Cl": 0.988, "SO4": 0.998, "HCO3": 0.983, "Ba": 0.998,
        "Sr": 0.998, "F": 0.975, "SiO2": 0.99, "B": 0.77,
        "NO3": 0.945, "PO4": 0.997, "NH4": 0.89,
    },
}
```

**Step 2 — For NF membranes ONLY, also add:**
```python
"nf_ps": {      # Per-ion solute permeability Ps (m/s); higher = more passage
    "Ca": 1.0e-8,   # divalent cations -- very low Ps (high rejection)
    "Mg": 1.0e-8,
    "SO4": 1.5e-8,  # divalent anions -- very low Ps
    "Na": 2.5e-7,   # monovalent -- higher passage
    "Cl": 4.0e-7,
    "HCO3": 2.0e-7,
    "NO3": 3.5e-7,
    "K": 2.8e-7,
    "B": 1.0e-6,    # boron passes readily
},
"E_Aw_over_R": 4200.0,  # from manufacturer TCF specification sheet
```

**How to calculate A and B from manufacturer test data:**
```
Given:
  Test pressure  P_test  (bar)
  Test feed TDS  TDS_f   (mg/L)
  Temperature    T_test  (degC)
  Recovery       r_test  (decimal)
  Permeate flow  Qp      (m3/h)
  Rejection      R       (decimal)

Step 1: estimate osmotic pressure of average concentration:
  CF = 1 / (1 - r_test)
  pi_avg = (TDS_f * (1 + CF) / 2) * 0.7 / 1000  [bar, rough]

Step 2: NDP = P_test - pi_avg

Step 3: TCF = exp(2640 * (1/298.15 - 1/(T_test+273.15)))

Step 4: A (LMH/bar) = (Qp * 1000) / (active_area_m2 * NDP * TCF)

Step 5: B (m/s) ≈ A * (1 - R) / R * (1/3600) * 0.001 * 3.6
        (rough approximation -- use manufacturer Ps data if available)
```

**Step 3 — Verify:** Call `GET /api/membranes`. The new membrane should appear in `ro_membranes`.

**Step 4 — Auto-recommendation:** For the membrane to appear in `POST /api/recommend-membrane`, ensure `manufacturer == "Permionics"`. The recommender filters to Permionics membranes only.

---

### 14.2 Adding a New UF Module

**File to modify:** `backend/membrane_database.py` ONLY.

**Step 1 — Add the entry to `MembraneDatabase.UF_MODULES`:**

```python
"MY-NEW-UF-MODULE": {
    "type": "UF",
    "manufacturer": "Permionics",
    "membrane_area_m2": 75.0,            # From datasheet
    "fiber_id_mm": 0.8,
    "max_filtration_flux_lmh": 180.0,    # Max flux from datasheet
    "design_flux_lmh": 40.0,             # Recommended operating flux
    "clean_tmp_max_bar": 1.2,            # From datasheet
    "fouled_tmp_max_bar": 2.1,           # Typically 1.5-2x clean TMP max
    "max_tmp_bar": 2.5,
    "backwash_flux_lmh": 150.0,
    "backwash_duration_s": 45,
    "air_scour_flow_m3h": 12.0,
    "min_forward_flush_m3h": 1.5,
    "permeability_Lp20": 400.0,          # LMH/bar at 20 degC from datasheet
    "unit_cost_inr": 120000.0,           # Rs per module
    "feed_pump_kw_per_module": 0.75,     # kW
    "backwash_pump_kw_per_module": 1.1,  # kW
}
```

**How the UF engine uses each field:**

| Field | How used |
|---|---|
| `membrane_area_m2` | Module count = ceil(gross_flow / (design_flux * area / 1000)) |
| `design_flux_lmh` | Operating flux and module sizing target |
| `backwash_duration_s`, `backwash_flux_lmh` | Backwash water loss per cycle |
| `permeability_Lp20` | Clean TMP = actual_flux / (Lp20 * viscosity_correction) |
| `clean_tmp_max_bar`, `fouled_tmp_max_bar` | Warning generation |
| `feed_pump_kw_per_module` | Economic CAPEX/OPEX |
| `backwash_pump_kw_per_module` | Economic CAPEX/OPEX |
| `unit_cost_inr` | CAPEX calculation |

**Step 2 — Verify:** Call `GET /api/membranes`. New module appears in `uf_modules`.

---

### 14.3 Adding a New Technology Train (Similar to Existing)

**Example:** Adding `"MBR+RO"` (Membrane Bioreactor pre-treatment followed by RO).

**Files to modify:** `backend/system_engine.py`, `backend/server.py`

**Step 1 — `system_engine.py` -> `calculate_system()`:**

The routing is a string-check pattern. Locate the existing block and extend it:

```python
def calculate_system(self, input_data):
    train = input_data.get("technology_train", "RO")
    feed  = input_data["feed_water"]

    # Step 1: UF or MBR pre-treatment
    uf_res  = None
    mbr_res = None

    if "UF" in train:
        uf_res = self.uf_engine.simulate_uf(...)

    if "MBR" in train:
        # MBR significantly reduces turbidity, TSS, and TOC
        # Model as a UF-equivalent in terms of hydraulics:
        mbr_feed_flow = input_data["target_flow_m3h"] / (1 - mbr_backwash_loss)
        mbr_res = self.uf_engine.simulate_uf(
            gross_feed_flow_m3h = mbr_feed_flow,
            uf_module = input_data.get("uf_module", "PERMA-UF-i0875s40"),
            temp_c    = feed.get("temperature", 25.0),
            design_flux_override = 15.0  # MBR runs at lower flux
        )
        # MBR permeate has much lower TOC -- adjust for downstream calculations
        ro_feed_ions = feed.copy()
        ro_feed_ions["toc"] = min(feed.get("toc", 2.0) * 0.1, 0.5)

    # Step 2: RO simulation (unchanged)
    if "RO" in train or "NF" in train:
        # ... existing bisection + simulate_system call
```

**Step 2 — `system_engine.py` -> `__init__()`:** Import any new engine if needed.

**Step 3 — `server.py` -> `SystemCalcInput`:** Add any new configuration fields specific to MBR (e.g., `mbr_flux_lmh`, `mbr_srt_days`).

**Step 4 — `server.py` -> routing block in `calculate_system` endpoint:** No changes needed since `SystemEngine.calculate_system()` handles train detection internally.

**Step 5 — `server.py` -> `_run_projection_core()`:** Ensure the new train name is handled correctly by the physics engine call (the physics engine currently reads `technology_train` to decide whether to use 2P-RO branches).

**Step 6 — `report_generator.py`:** Add a new section method for MBR results and call it from `generate_calculation_report()`.

---

### 14.4 Adding a Completely New Technology Train

**Example:** Adding `"ED"` (Electrodialysis).

**Step 1 — Create `backend/ed_engine.py`:**

```python
"""
Electrodialysis (ED) Calculation Engine
Physics: Nernst-Planck ion transport, Faraday's law
"""
from typing import Dict, Any, List

class EDEngine:
    def simulate_ed(
        self,
        feed_flow_m3h: float,
        feed_ions: Dict[str, float],
        target_recovery_pct: float,
        stack_count: int,
        cell_pairs: int,
        current_density_am2: float,
        temp_c: float
    ) -> Dict[str, Any]:
        """
        Simulate an ED system.

        Returns dict with keys:
          overview:        {current_A, voltage_V, power_kW, stack_count}
          diluate_ions:    {ion: concentration_mg_L}
          concentrate_ions:{ion: concentration_mg_L}
          diluate_flow_m3h: float
          system_recovery: float
          warnings:        list
        """
        # Faraday's law: equivalents removed per Faraday of charge
        F = 96485  # C/mol
        # ... implement your ED transport equations here
        pass
```

**Step 2 — `system_engine.py`:**

```python
from ed_engine import EDEngine

class SystemEngine:
    def __init__(self):
        self.uf_engine = UFEngine()
        self.ro_engine = ROEngine()
        self.ed_engine = EDEngine()   # ADD

    def calculate_system(self, input_data):
        train = input_data.get("technology_train", "RO")
        ...
        # NEW: ED branch
        if "ED" in train and "RO" not in train:
            ed_res = self.ed_engine.simulate_ed(
                feed_flow_m3h       = input_data["target_flow_m3h"],
                feed_ions           = ions,
                target_recovery_pct = input_data["target_recovery_pct"],
                stack_count         = input_data.get("ed_stack_count", 2),
                cell_pairs          = input_data.get("ed_cell_pairs", 200),
                current_density_am2 = input_data.get("ed_current_density", 400),
                temp_c              = feed.get("temperature", 25.0)
            )
            result["ed_results"] = ed_res
            # Extract key outputs:
            result["diluate_tds"] = sum(ed_res["diluate_ions"].values())
            return result
```

**Step 3 — `server.py` -> `SystemCalcInput`:**
```python
class SystemCalcInput(BaseModel):
    ...
    ed_stack_count:      Optional[int]   = 2
    ed_cell_pairs:       Optional[int]   = 200
    ed_current_density:  Optional[float] = 400.0  # A/m2
```

**Step 4 — Economics:** In `system_engine.py`, add the ED economic calculation block:
```python
if "ED" in train and eco_params:
    ed_electrode_cost = eco_params.get("ed_electrode_cost", 50000)
    ed_stack_cost     = stack_count * ed_electrode_cost * cell_pairs
    # ... add to CAPEX / OPEX
```

**Step 5 — Physics projection:** The `_run_projection_core()` in `server.py` currently only models RO/NF aging. For ED, create a separate aging sub-model or skip physics projection for now and document accordingly.

**Step 6 — Report:** Add `_write_ed_section(doc, result)` in `report_generator.py`.

**Step 7 — Frontend:** Add `"ED"` to the technology train dropdown in `ui_ux_design/index.html`, and handle `ed_results` in the JavaScript display logic.

---

### 14.5 Adding a New Scalant to the PHREEQC Calculations

**Files to modify:** `backend/server.py`

**Step 1 — Find the concentrate SI query block** in `calculate_system` endpoint (~line 470 in server.py). Add the new mineral phase using the exact name from the PHREEQC database:

```python
result["concentrate_si"] = {
    "Calcite":    round(sol.si("Calcite"),   3),
    "Aragonite":  round(sol.si("Aragonite"), 3),
    "Dolomite":   round(sol.si("Dolomite"),  3),
    "Gypsum":     round(sol.si("Gypsum"),    3),
    "Anhydrite":  round(sol.si("Anhydrite"), 3),
    "Barite":     round(sol.si("Barite"),    3),
    "Celestite":  round(sol.si("Celestite"), 3),
    "Fluorite":   round(sol.si("Fluorite"),  3),
    "SiO2(a)":   round(sol.si("SiO2(a)"),   3),
    "Vivianite":  round(sol.si("Vivianite"), 3),   # <-- ADD HERE
}
```

**Step 2 — Repeat in `_run_projection_core()`** (same block).

**Step 3 — Repeat in `calculate_scaling()` endpoint** (feed water SI calculation).

**Step 4 — For NF-specific analytical scaling** (not PHREEQC), add to `_compute_nf_concentrate_scaling()` in `system_engine.py`:

```python
# Example: MgF2 (Sellaite) -- Ksp = 5.16e-11
Ksp_mf2 = 5.16e-11
ip_mf2  = mol("Mg") * (mol("F") ** 2) * gamma(2) * (gamma(1) ** 2)
si_mf2  = math.log10(ip_mf2 / Ksp_mf2) if ip_mf2 > 1e-30 else -99.0
results["MgF2_sellaite"] = {
    "SI": round(si_mf2, 3),
    "risk": "HIGH" if si_mf2 > 0 else ("MODERATE" if si_mf2 > -0.5 else "LOW"),
    "antiscalant_required": si_mf2 > 0
}
```

**Step 5 — Add to aging engine if needed.** Add the new mineral to `MINERAL_PARAMS` in `physics_aging_engine.py`:
```python
MINERAL_PARAMS = {
    ...
    "Vivianite": {
        "n": 2,
        "gamma_m": 0.5e-7,     # surface energy J/m2
        "k_g": 2.0e-9,         # crystal growth rate m/s
        "alpha_scale": 3.0e10, # specific resistance m/kg
        "M_w": 0.5016,         # molar weight kg/mol
        "delta_si_antiscalant": 0.2,
        "cip_rev_frac": 0.70,
        "cip_irrev_frac": 0.30
    },
}
```

---

### 14.6 Adding a New Feed Water Ion Parameter

**Example:** Adding `"lithium"` (Li+, a monovalent cation, z=1, MW=6.941).

**Step 1 — `server.py` -> `FeedWaterData`:**
```python
class FeedWaterData(BaseModel):
    ...
    lithium: float = 0.0   # Li+ (mg/L)
```

**Step 2 — `server.py` -> `AutoBalanceInput`:**
```python
class AutoBalanceInput(BaseModel):
    ...
    lithium: float = 0.0
```

**Step 3 — `server.py` -> `auto_balance()` endpoint** -> cation sum:
```python
mw_li, z_li = 6.941, 1
cat_meq += (data.lithium / mw_li) * z_li
```

**Step 4 — `server.py` -> `calculate_scaling()` and concentrate solution building** -> add PHREEQC species:
```python
sol_input = {
    ...
    'Li': data.lithium,   # PHREEQC element symbol
}
```

**Step 5 — `system_engine.py` -> all `ions` extraction blocks:**
```python
ions = {
    ...
    "Li": feed.get("lithium", 0),
}
```

**Step 6 — `calc_engine.py` -> `ROEngine`:**
- Add to molar mass dict: `self.MM["Li"] = 6.941`
- In `simulate_element()`, sigma will be read from the membrane database. Add `"Li"` to each membrane's `sigma` dict in `membrane_database.py`, or handle missing keys with a default:
  ```python
  sigma = sigmas.get(ion, 0.985)   # Default for unrecognised monovalent cations
  ```

**Step 7 — `membrane_database.py`:** Add `"Li": 0.985` to the `sigma` dict of all relevant membranes, or rely on the default fallback above.

**Step 8 — `server.py` -> PHREEQC concentrate solution building** (inside `_run_projection_core` and the main `calculate_system` endpoint):
```python
sol_input = {
    ...
    'Li': conc_ions.get("Li", 0),
}
```

---

### 14.7 Adding a New Fouling Sub-Model to the Aging Engine

**File to modify:** `backend/physics_aging_engine.py`

**Step 1 — Add new constants to `DEFAULT_PHYSICS_PARAMS`:**
```python
DEFAULT_PHYSICS_PARAMS: Dict[str, float] = {
    ...
    # Sub-model VI: Colloidal silica fouling
    "k_sil_dep":  1.0e-6,   # Silica deposition rate constant
    "k_sil_rem":  5.0e-9,   # Silica shear removal rate constant
    "alpha_sil":  2.5e10,   # Specific resistance of silica deposit (m/kg)
}
```

**Step 2 — Add state variable to element state initialisation in `run_physics_projection()`:**
```python
state = {
    "R_cake":   0.0,
    "L_bio":    1e-9,
    "m_scale":  0.0,
    "q_nom":    0.0,
    "eps_c":    0.0,
    "m_silica": 0.0,   # <-- ADD NEW STATE VARIABLE
}
```

**Step 3 — Implement the ODE in the monthly time loop:**
```python
# ---- Sub-model VI: Colloidal Silica Fouling ----
sio2_conc = feed_ions.get("SiO2", 0) * CF_local   # concentrate SiO2
sio2_threshold = 100.0  # mg/L -- no deposit below this
if sio2_conc > sio2_threshold:
    dm_sil_dep = params["k_sil_dep"] * (sio2_conc - sio2_threshold) * jv
    dm_sil_rem = params["k_sil_rem"] * tau_w * state["m_silica"]
    state["m_silica"] += (dm_sil_dep - dm_sil_rem) * DT_H * 3600
    state["m_silica"] = max(0.0, state["m_silica"])

R_silica = params["alpha_sil"] * state["m_silica"]
```

**Step 4 — Include new resistance in total resistance:**
```python
R_total = R_m + R_cake + R_bio + R_scale + R_NOM + R_compaction + R_silica
#                                                              ^^ ADD
```

**Step 5 — Add CIP cleanup:**
```python
if cip_triggered:
    ...
    # Silica deposit is partially removed by alkaline CIP
    eps_silica_alkali = 0.60   # 60% removal
    state["m_silica"] *= (1 - eps_silica_alkali)
```

**Step 6 — Export sub-model contribution in annual snapshots:**
```python
snap = {
    ...
    "R_silica_contrib": R_silica / R_total if R_total > 0 else 0,
}
```

**Step 7 — Add to `mechanism_totals`:**
```python
mechanism_totals["Silica Fouling"] += R_silica * DT_H
```

---

### 14.8 Adding a New Economic Parameter

**Example:** Adding explicit antiscalant chemical dosing cost.

**Step 1 — `server.py` -> `EconomicParams`:**
```python
class EconomicParams(BaseModel):
    ...
    antiscalant_dose_g_m3:    float = 3.0    # g per m3 of product
    antiscalant_cost_inr_kg:  float = 200.0  # Rs per kg
```

**Step 2 — `system_engine.py` -> economic calculation block:**
```python
dose_g_m3  = eco_params.get("antiscalant_dose_g_m3", 3.0)
cost_kg    = eco_params.get("antiscalant_cost_inr_kg", 200.0)
q_pa_m3    = summary.get("perm_flow", 0) * hours_pa
as_kg_pa   = dose_g_m3 / 1000.0 * q_pa_m3
as_cost_pa = as_kg_pa * cost_kg

total_opex_pa += as_cost_pa
result["economics"]["opex"]["antiscalant_cost_pa_inr"] = round(as_cost_pa, 2)
```

**Step 3 — `report_generator.py`:** Add the new line item to the OPEX table generation section.

---

### 14.9 Adding a New API Endpoint

**File to modify:** `backend/server.py`

**Step 1 — Define a Pydantic request model** (if needed):
```python
class MyNewInput(BaseModel):
    param1: float
    param2: str = "default_value"
```

**Step 2 — Add the FastAPI route:**
```python
@app.post("/api/my-new-endpoint")
def my_new_endpoint(data: MyNewInput):
    """
    Short description of what this endpoint does.

    Request: MyNewInput
    Response: dict with output fields
    """
    try:
        # Call your engine or compute logic
        result = some_engine.do_something(data.param1, data.param2)
        return {"output": result, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 3 — Authentication:** All `/api/` routes are automatically protected by `BasicAuthASGIMiddleware`. To make an endpoint public, add a path exclusion in the middleware's `__call__` method:
```python
PUBLIC_PATHS = ["/api/verify-auth", "/api/my-public-endpoint"]
if scope.get("path") in PUBLIC_PATHS:
    await self.app(scope, receive, send)
    return
```

**Step 4 — Frontend:** Add the `fetch()` call with Basic Auth header:
```javascript
const response = await fetch('/api/my-new-endpoint', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + btoa(username + ':' + password)
    },
    body: JSON.stringify({ param1: 42.0, param2: "value" })
});
const data = await response.json();
```

---

### 14.10 Modifying the Report Output

**File to modify:** `backend/report_generator.py`

The report generator uses `python-docx`. Key patterns:

**Adding a new table section:**
```python
def _write_my_new_section(self, doc, result):
    """Add a new data section to the report."""
    doc.add_heading("My New Section Title", level=2)

    data = result.get("my_new_data_key", {})
    if not data:
        doc.add_paragraph("No data available.")
        return

    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"

    # Header row
    hdr = table.rows[0].cells
    hdr[0].text = "Parameter"
    hdr[1].text = "Value"
    hdr[2].text = "Unit"
    # Style header cells bold
    for cell in hdr:
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True

    # Data rows
    for param_name, value in data.items():
        row = table.add_row().cells
        row[0].text = param_name
        row[1].text = str(round(float(value), 3)) if isinstance(value, (int, float)) else str(value)
        row[2].text = "mg/L"   # adjust unit as needed
```

**Calling the new method from `generate_calculation_report()`:**
```python
def generate_calculation_report(self, result, output_path):
    doc = Document()
    self._write_cover_page(doc, result)
    self._write_feed_water_section(doc, result)
    self._write_system_config_section(doc, result)
    # ... existing sections ...
    self._write_my_new_section(doc, result)   # <-- ADD HERE
    doc.save(output_path)
```

**Adding a chart/figure:**
```python
import matplotlib.pyplot as plt
import io

def _write_trend_chart(self, doc, snapshots):
    """Embed a matplotlib chart showing NPF vs year."""
    years = [s["year"] for s in snapshots]
    npf   = [s["npf"]  for s in snapshots]

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(years, npf, "b-o", label="NPF")
    ax.set_xlabel("Year"); ax.set_ylabel("NPF")
    ax.set_title("Normalised Permeate Flow Trend")
    ax.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    buf.seek(0)
    plt.close(fig)

    doc.add_picture(buf, width=Inches(5.5))
```

---

## 15. File Map Quick Reference

```
intern_proj/
|
+-- Dockerfile                  Container build (Python 3.11-slim + LibreOffice)
+-- requirements.txt            Python dependencies (7 packages)
+-- start.bat                   Windows local start script
|
+-- backend/
|   +-- run_app.py             ENTRY POINT: mounts frontend + starts Uvicorn
|   +-- server.py              API layer (FastAPI, all endpoints, auth, PHREEQC)
|   +-- system_engine.py       Orchestration: UF+RO, 2P-RO, NF, recycle
|   +-- calc_engine.py         RO/NF element & system mass transport physics
|   +-- uf_engine.py           UF sizing, TMP, backwash cycle, warnings
|   +-- membrane_database.py   ALL membrane/UF specs  <-- ADD MEMBRANES HERE
|   +-- process_engine.py      7-phase technology recommendation
|   +-- membrane_recommender.py Multi-criteria membrane scoring
|   +-- conditioning.py        Interstage pH adjustment (2P-RO)
|   +-- physics_aging_engine.py PRIMARY aging model (5 sub-models + CIP)
|   +-- aging_engine.py        DEPRECATED legacy aging engine (do not use)
|   +-- report_generator.py    WAVE-style PDF report generator
|   +-- phreeqc.dat            PHREEQC thermodynamic database
|   +-- llnl.dat               LLNL alternative PHREEQC database
|
+-- ui_ux_design/
    +-- index.html             Frontend SPA (served as static files at /)
```

**Where to make changes for common tasks:**

| Task | File |
|---|---|
| Add a new RO/NF membrane | `membrane_database.py` -> `RO_MEMBRANES` dict |
| Add a new UF module | `membrane_database.py` -> `UF_MODULES` dict |
| Add a new technology train | `system_engine.py` + `server.py` |
| Add a new feed water ion | `server.py` + `system_engine.py` + `calc_engine.py` + `membrane_database.py` |
| Add a new scalant | `server.py` (PHREEQC block) + `system_engine.py` (NF analytical) |
| Change aging physics | `physics_aging_engine.py` |
| Add a new API endpoint | `server.py` |
| Modify PDF report | `report_generator.py` |
| Change authentication | `server.py` -> `BasicAuthASGIMiddleware` |
| Change default economic assumptions | `system_engine.py` -> economic block |

---

## 16. Glossary

| Term | Definition |
|---|---|
| **A** | Water permeability coefficient (LMH/bar) — governs flux per unit of NDP |
| **B** | Salt permeability coefficient (m/s) — governs salt passage through the active layer |
| **Beta** | Concentration polarization factor = surface concentration / bulk concentration |
| **BWRO** | Brackish Water Reverse Osmosis (operating pressure typically 10-41 bar) |
| **CAPEX** | Capital Expenditure — one-time cost of equipment and installation |
| **CBE** | Charge Balance Error (%) — measure of feed water analysis quality |
| **CEB** | Chemical Enhanced Backwash — periodic chemical cleaning of UF membranes |
| **CF** | Concentration Factor = 1 / (1 - recovery) |
| **CIP** | Clean-In-Place — chemical cleaning of RO membranes to restore performance |
| **CP** | Concentration Polarization — ion enrichment at the membrane surface |
| **CRF** | Capital Recovery Factor — annualises a capital cost over project life at a discount rate |
| **Davies equation** | Extension of Debye-Hückel for ionic-strength-dependent activity coefficients |
| **FRI** | Fouling Resistance Index — normalised total hydraulic resistance increase |
| **GFD** | Gallons per square foot per day (1 GFD = 1.6985 LMH) |
| **IAP** | Ion Activity Product — used in computing Saturation Index |
| **Ksp** | Solubility product constant |
| **LMH** | Litres per square metre per hour (membrane flux unit) |
| **LSI** | Langelier Saturation Index for CaCO3 (= measured pH - saturation pH) |
| **NDP** | Net Driving Pressure = P_feed - P_backpressure - delta_osmotic |
| **NF** | Nanofiltration — partially rejects divalent ions, passes monovalents |
| **NOM** | Natural Organic Matter — precursor to biofouling and fouling layer formation |
| **NPF** | Normalised Permeate Flow (ASTM D4516-19a) — measure of flux decline |
| **NSP** | Normalised Salt Passage (ASTM D4516-19a) — measure of rejection decline |
| **OPEX** | Operating Expenditure — recurring annual cost |
| **pHs** | Saturation pH — pH at which CaCO3 is exactly in equilibrium with the water |
| **RO** | Reverse Osmosis — high-pressure membrane process to reject dissolved salts |
| **SDI** | Silt Density Index — measure of feed water colloidal/particulate fouling potential |
| **SEC** | Specific Energy Consumption (kWh per m3 permeate) |
| **SI** | Saturation Index = log10(IAP/Ksp) — positive means scaling risk |
| **Sigma** | Spiegler-Kedem reflection coefficient (0=no rejection, 1=perfect rejection) |
| **SWRO** | Seawater Reverse Osmosis (operating pressure typically 55-80 bar) |
| **TCF** | Temperature Correction Factor — normalises permeability measurement to 25 degC |
| **TDS** | Total Dissolved Solids (mg/L) |
| **TMP** | Trans-Membrane Pressure — driving pressure across a UF membrane |
| **TOC** | Total Organic Carbon (mg/L) — biofouling precursor |
| **TSS** | Total Suspended Solids (mg/L) |
| **UF** | Ultrafiltration — low-pressure membrane removing suspended solids and colloids |
| **2P-RO** | Two-Pass Reverse Osmosis — Pass 1 permeate feeds Pass 2 for ultra-high purity |

---

*End of PACE Codebase Documentation. Last updated: July 2026.*
