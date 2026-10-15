# PACE — `server.py` Technical Documentation (Feed Data & API Layer)

**File:** `backend/server.py` | 1,325 lines | 58,058 bytes
**Framework:** FastAPI + Uvicorn
**Source of truth:** Direct source code analysis

---

## 1. Purpose & Scope

`server.py` is the **API gateway** of PACE. It:

1. Defines all **Pydantic data models** (input schemas) for every request the frontend sends.
2. Implements **authentication middleware** (HTTP Basic Auth on all `/api/` routes).
3. Exposes every **REST endpoint** — orchestrating `SystemEngine`, `ProcessRecommendationEngine`, `PhysicsAgingEngine`, `MembraneRecommender`, and `ReportGenerator`.
4. Performs **post-processing** (concentrate PHREEQC SI, charge balance, watermarking) not belonging to any individual engine.

---

## 2. Authentication (Lines 20–79)

### `BasicAuthASGIMiddleware`

Applied as the **first** middleware on the ASGI stack. Intercepts every HTTP and WebSocket request.

**Rules:**
- `OPTIONS` requests: always pass through (CORS preflight)
- Paths **not** starting with `/api/`: always pass through (serves frontend static files)
- `/api/` paths: require `Authorization: Basic <base64(user:pass)>`

**Credential check:**
```
expected_user = os.environ.get("API_USERNAME", "pace_permionics")
expected_pass = os.environ.get("API_PASSWORD", "satyaraj_permionics@2026")
```

Credentials are sourced from environment variables; defaults are hardcoded as fallbacks.

**On failure:** Returns HTTP 401 with body `"Unauthorized"`.

---

## 3. CORS Configuration (Lines 81–89)

```python
allow_origins=[],           # no origin whitelist
allow_origin_regex=".*",    # all origins allowed
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

All origins are permitted via regex `".*"` — intended for internal/intranet deployment behind the Basic Auth layer.

---

## 4. PHREEQC Initialisation (Line 92)

```python
pp = phreeqpython.PhreeqPython(database='phreeqc.dat')
```

A single shared PHREEQC instance (`pp`) is created at module load and reused across all endpoints. The database file used is `phreeqc.dat` (standard PHREEQC thermodynamic database).

---

## 5. Input Data Models

### 5.1 `FeedWaterData` (Lines 94–118)

Primary feed water input for scaling and system simulation.

| Field | Type | Default | Units |
|---|---|---|---|
| `temperature` | float | 25.0 | °C |
| `ph` | float | 7.0 | — |
| `calcium` | float | 0.0 | mg/L |
| `magnesium` | float | 0.0 | mg/L |
| `sodium` | float | 0.0 | mg/L |
| `chloride` | float | 0.0 | mg/L |
| `sulfate` | float | 0.0 | mg/L |
| `bicarbonate` | float | 0.0 | mg/L |
| `strontium` | float | 0.0 | mg/L |
| `fluoride` | float | 0.0 | mg/L |
| `silica` | float | 0.0 | mg/L |
| `barium` | float | 0.0 | mg/L |
| `potassium` | float | 0.0 | mg/L |
| `ammonium` | float | 0.0 | mg/L |
| `carbonate` | float | 0.0 | mg/L |
| `nitrate` | float | 0.0 | mg/L |
| `aluminium` | float | 0.0 | mg/L |
| `iron` | float | 0.0 | mg/L |
| `manganese` | float | 0.0 | mg/L |
| `phosphate` | float | 0.0 | mg/L |
| `tss` | Optional[float] | 0.0 | mg/L |
| `turbidity` | Optional[float] | 0.0 | NTU |
| `tds` | Optional[float] | 0.0 | mg/L |

> **Note:** `FeedWaterData` is used for the **feed scaling** endpoint (`/api/calculate-scaling`). The system simulation endpoints (`/api/calculate-system`, `/api/calculate-system-physics`) receive feed water as a raw `dict` inside `SystemCalcInput.feed_water` and `PhysicsCalcInput.feed_water`.

---

### 5.2 `AutoBalanceInput` (Lines 119–136)

Input for the charge balance / auto-balance endpoint. Subset of `FeedWaterData` — includes all ions needed for charge balance calculation but not physical parameters (TSS, turbidity, TDS).

| Field | Type | Default | Units |
|---|---|---|---|
| `calcium` | float | 0.0 | mg/L |
| `magnesium` | float | 0.0 | mg/L |
| `sodium` | float | 0.0 | mg/L |
| `potassium` | float | 0.0 | mg/L |
| `ammonium` | float | 0.0 | mg/L |
| `barium` | float | 0.0 | mg/L |
| `strontium` | float | 0.0 | mg/L |
| `chloride` | float | 0.0 | mg/L |
| `sulfate` | float | 0.0 | mg/L |
| `bicarbonate` | float | 0.0 | mg/L |
| `carbonate` | float | 0.0 | mg/L |
| `nitrate` | float | 0.0 | mg/L |
| `fluoride` | float | 0.0 | mg/L |
| `phosphate` | float | 0.0 | mg/L |
| `silica` | float | 0.0 | mg/L |
| `ph` | float | 7.0 | — |
| `temperature` | float | 25.0 | °C |

---

### 5.3 `BalanceResult` (Lines 138–148)

Response model for `/api/auto-balance`:

| Field | Description |
|---|---|
| `status` | `"BALANCED"` or `"ADJUSTED"` |
| `cbe_meq` | Charge balance error in meq/L |
| `cbe_pct` | CBE as percentage of total equivalents |
| `sum_cations_meq` | Total cation equivalents (meq/L) |
| `sum_anions_meq` | Total anion equivalents (meq/L) |
| `injected_ion` | `"Na"` or `"Cl"` if adjustment made, else `null` |
| `injected_amount_mg_l` | Amount of ion added (mg/L) |
| `na_final` | Final Na concentration after adjustment |
| `cl_final` | Final Cl concentration after adjustment |
| `message` | Human-readable status message |

---

### 5.4 `EconomicParams` (Lines 150–163)

| Field | Default | Units |
|---|---|---|
| `electricity_tariff` | 7.50 | ₹/kWh |
| `membrane_cost` | 26,880 | ₹/element |
| `vessel_cost` | 48,000 | ₹/vessel |
| `pump_cost_kw` | 96,000 | ₹/kW |
| `ic_factor` | 0.15 | — (installation %) |
| `contingency_factor` | 0.10 | — |
| `plant_availability` | 0.90 | fraction |
| `membrane_lifetime` | 5.0 | years |
| `discount_rate` | 0.10 | — |
| `project_life` | 20.0 | years |
| `uf_module_cost` | None | ₹/module (user override; DB value used if None) |
| `uf_membrane_lifetime` | 7.0 | years |

---

### 5.5 `PassConfig` (Lines 164–169)

Per-pass RO configuration for two-pass systems:

| Field | Description |
|---|---|
| `membrane` | Membrane model string |
| `stages` | Number of stages |
| `vessels_per_stage` | List[int] — vessels in each stage |
| `elements_per_vessel` | Elements per pressure vessel |
| `target_recovery_pct` | Target recovery % for this pass |

---

### 5.6 `ConditioningConfig` (Lines 171–175)

| Field | Default | Description |
|---|---|---|
| `enabled` | False | Whether inter-pass conditioning is active |
| `target_ph` | None | Target pH after conditioning |
| `chemical` | None | Conditioning chemical |
| `co2_degassing` | False | Whether CO₂ degassing is applied |

---

### 5.7 `RecycleConfig` (Lines 177–179)

| Field | Default | Description |
|---|---|---|
| `enabled` | False | Whether concentrate recycle is active |
| `recycle_ratio` | 0.0 | Fraction of concentrate recycled to feed |

---

### 5.8 `SystemCalcInput` (Lines 181–207)

Main input for system simulation and report generation:

| Field | Type | Default | Description |
|---|---|---|---|
| `technology_train` | str | — | e.g. `"RO"`, `"UF+RO"`, `"2P-RO"`, `"UF+2P-RO"` |
| `feed_water` | dict | — | Ion concentrations + temp + pH |
| `target_flow_m3h` | float | — | Desired permeate flow (m³/h) |
| `target_recovery_pct` | float | — | Target system recovery (%) |
| `target_tds` | Optional[float] | 50.0 | Target permeate TDS (mg/L) |
| `source_type` | Optional[str] | `"LOW_TDS"` | Feed source classification |
| `ro_membrane` | str | — | RO membrane model (from MembraneDatabase) |
| `uf_module` | Optional[str] | None | UF module model |
| `stages` | int | — | Number of RO stages |
| `vessels_per_stage` | List[int] | — | Vessels per stage |
| `elements_per_vessel` | int | — | Elements per vessel |
| `economic_params` | Optional[EconomicParams] | None | Economic parameters |
| `recycle_enabled` | Optional[bool] | False | Concentrate recycle on/off |
| `recycle_ratio` | Optional[float] | 0.0 | Recycle fraction |
| `pass1` | Optional[PassConfig] | None | Pass 1 config (2P-RO only) |
| `pass2` | Optional[PassConfig] | None | Pass 2 config (2P-RO only) |
| `conditioning` | Optional[ConditioningConfig] | None | Inter-pass conditioning |
| `recycle` | Optional[RecycleConfig] | None | Recycle configuration |
| `aging_results` | Optional[dict] | None | Aging results for report attachment |
| `pfd_svg` | Optional[str] | None | PFD SVG for report |
| `pfd_png` | Optional[str] | None | PFD PNG for report |
| `project_details` | Optional[dict] | None | Project metadata for report |
| `physics_results` | Optional[dict] | None | Physics projection results for report |
| `physics_selected_year` | Optional[int] | 0 | Selected projection year for report |
| `units` | Optional[dict] | None | Unit display preferences |

---

### 5.9 `PhysicsFeedQuality` (Lines 720–726)

Physics projection feed quality (sourced from Feed Data tab):

| Field | Default | Units | Description |
|---|---|---|---|
| `sdi15` | 3.0 | — | SDI-15 index |
| `toc_mg_l` | 2.0 | mg/L | Total organic carbon |
| `cl2_residual_mg_l` | 0.0 | mg/L | Free chlorine post-SBS dosing |

---

### 5.10 `PhysicsCIPConfig` (Lines 728–736)

CIP protocol for physics projection:

| Field | Default | Description |
|---|---|---|
| `acid_ph` | 2.5 | Acid CIP step target pH |
| `alk_ph` | 11.5 | Alkaline CIP step target pH |
| `interval_months` | 0 | 0 = dynamic condition-triggered; >0 = scheduled |
| `duration_h` | 4.0 | Duration per CIP step (hours) |

---

### 5.11 `AgingSystemConfig` (Lines 686–691)

| Field | Description |
|---|---|
| `membrane` | Membrane model |
| `stages` | Number of stages |
| `vessels_per_stage` | List[int] |
| `elements_per_vessel` | Elements per vessel |
| `target_recovery_pct` | Recovery target (%) |

### 5.12 `AgingConfig` (Lines 693–700)

| Field | Default | Description |
|---|---|---|
| `design_life_months` | 60 | Total simulation period (months) |
| `time_step_months` | 1 | Integration timestep (months) |
| `simulation_mode` | `"constant_recovery"` | `"constant_recovery"` or `"constant_pressure"` |
| `cip_trigger` | `"scheduled"` | `"scheduled"` or `"performance"` |
| `cip_interval_days` | 90 | CIP interval (0 = dynamic) |
| `cip_type` | `"acid_alkaline_sequential"` | CIP chemical type |
| `antiscalant_dosed` | True | Whether antiscalant is dosed |

### 5.13 `FeedHistory` (Lines 702–706)

| Field | Default | Units |
|---|---|---|
| `sdi15` | 3.0 | — |
| `toc_mg_l` | 2.0 | mg/L |
| `temperature_c` | 28.0 | °C |
| `cl2_residual_mg_l` | 0.0 | mg/L |

---

## 6. API Endpoints

### 6.1 `GET /` (Line 209)
Redirects to `/index.html` (serves the frontend SPA).

---

### 6.2 `POST /api/verify-auth` (Lines 213–215)
Returns `{"status": "success"}` if the request passes Basic Auth middleware. Used by the frontend login screen to validate credentials.

---

### 6.3 `POST /api/calculate-scaling` (Lines 217–268)

**Input:** `FeedWaterData`

Assembles a PHREEQC solution from all feed ions and returns Saturation Indices (SI) for 10 mineral phases.

**PHREEQC ion mapping:**

| PACE field | PHREEQC key | Format |
|---|---|---|
| calcium | `Ca` | direct mg/L |
| magnesium | `Mg` | direct mg/L |
| sodium | `Na` | direct mg/L |
| potassium | `K` | direct mg/L |
| ammonium | `N(-3)` | `"{val} as NH4"` |
| chloride | `Cl` | direct mg/L |
| sulfate | `S(6)` | `"{val} as SO4"` |
| bicarbonate | `Alkalinity` | `"{val} as HCO3"` |
| nitrate | `N(5)` | `"{val} as NO3"` |
| strontium | `Sr` | direct mg/L |
| fluoride | `F` | direct mg/L |
| silica | `Si` | `"{val} as SiO2"` |
| barium | `Ba` | direct mg/L |
| aluminium | `Al` | direct mg/L |
| iron | `Fe` | direct mg/L |
| manganese | `Mn` | direct mg/L |
| phosphate | `P` | `"{val} as PO4"` |

**Output fields:**

| Field | Mineral Phase |
|---|---|
| `gypsum_si` | Gypsum |
| `calcite_si` | Calcite |
| `aragonite_si` | Aragonite |
| `barite_si` | Barite |
| `lsi` | Calcite SI (used as LSI proxy) |
| `celestite_si` | Celestite |
| `fluorite_si` | Fluorite |
| `anhydrite_si` | Anhydrite |
| `silica_si` | SiO₂(a) |
| `iron_si` | Fe(OH)₃(a) |
| `aluminium_si` | Al(OH)₃(a) |
| `manganese_si` | Pyrolusite |
| `calcium_phosphate_si` | Hydroxyapatite |

> **Note:** LSI is returned as Calcite SI — they are thermodynamically equivalent for the carbonate system in PHREEQC.

---

### 6.4 `POST /api/auto-balance` (Lines 270–358)

**Input:** `AutoBalanceInput` | **Output:** `BalanceResult`

#### Charge Balance Error (CBE) Calculation

**Molar weights and valences used:**

| Ion | MW (g/mol) | z |
|---|---|---|
| Ca²⁺ | 40.08 | 2 |
| Mg²⁺ | 24.31 | 2 |
| Na⁺ | 22.99 | 1 |
| K⁺ | 39.10 | 1 |
| NH₄⁺ | 18.04 | 1 |
| Ba²⁺ | 137.33 | 2 |
| Sr²⁺ | 87.62 | 2 |
| Cl⁻ | 35.45 | 1 |
| SO₄²⁻ | 96.06 | 2 |
| HCO₃⁻ | 61.02 | 1 |
| CO₃²⁻ | 60.01 | 2 |
| NO₃⁻ | 62.00 | 1 |
| F⁻ | 19.00 | 1 |
| PO₄³⁻ | 94.97 | 3 |

**Cation equivalents sum:**
$$\Sigma_{cat} = \frac{Ca}{40.08}\times2 + \frac{Mg}{24.31}\times2 + \frac{Na}{22.99} + \frac{K}{39.10} + \frac{NH_4}{18.04} + \frac{Ba}{137.33}\times2 + \frac{Sr}{87.62}\times2 \quad \text{(meq/L)}$$

**Anion equivalents sum:**
$$\Sigma_{an} = \frac{Cl}{35.45} + \frac{SO_4}{96.06}\times2 + \frac{HCO_3}{61.02} + \frac{CO_3}{60.01}\times2 + \frac{NO_3}{62.00} + \frac{F}{19.00} + \frac{PO_4}{94.97}\times3 \quad \text{(meq/L)}$$

**Charge balance error:**
$$CBE_{meq} = \Sigma_{cat} - \Sigma_{an}$$
$$CBE_{\%} = \frac{CBE_{meq}}{\max(\Sigma_{cat} + \Sigma_{an},\, 0.1)} \times 100$$

#### Auto-Balance Decision

| CBE condition | Action |
|---|---|
| $|CBE\%| \leq 2\%$ | Status = BALANCED, no adjustment |
| $CBE_{meq} > 0$ (excess cations) | Inject Cl⁻: `amount = CBE_meq × (35.45/1)` mg/L |
| $CBE_{meq} < 0$ (excess anions) | Inject Na⁺: `amount = |CBE_meq| × (22.99/1)` mg/L |

**Source:** Standard analytical chemistry CBE formula [VERIFIED — External]; injection of Na⁺/Cl⁻: [INTERNAL METHOD — Permionics standard practice]

---

### 6.5 `POST /api/process-recommendation` (Lines 360–367)

**Input:** `ProcessInputData` | **Output:** `ProcessRecommendationEngine` state dict

Delegates directly to `ProcessRecommendationEngine(pp).run(data)`. See `process_engine.md` for full documentation.

---

### 6.6 `POST /api/calculate-system` (Lines 369–524)

**Input:** `SystemCalcInput`

The main simulation endpoint. Routes to one of three engine paths:

| Condition | Engine call |
|---|---|
| `"2P-RO"` in `technology_train` | `engine.simulate_two_pass_system(input_dict)` |
| `recycle_enabled` and `recycle_ratio > 0` | `engine.calculate_system_with_recycle(input_dict)` |
| All other cases | `engine.calculate_system(input_dict)` |

**For 2P-RO results:** Pass 1 and Pass 2 results are merged into a single `ro_results` dict with system-level metrics overriding pass-level metrics (recovery, perm_flow, perm_tds, total_power_kw).

**Post-processing: Concentrate SI and pH** (Lines 420–518)

After simulation, the concentrate ion concentrations (`summary.conc_ions`) are used to compute PHREEQC SI on the concentrate stream.

**Concentrate pH estimation:**
$$pH_{conc} = pH_{feed} + \log_{10}\left(\frac{HCO_{3,conc}}{HCO_{3,feed}}\right)$$

If HCO₃ data unavailable, falls back to:
$$pH_{conc} = pH_{feed} + \log_{10}(CF), \quad CF = \frac{1}{1 - R/100}, \quad \text{capped to } [0, 14]$$

PHREEQC is then called with concentrate composition at `est_conc_ph`. Returns:
- `result["concentrate_ph"]` — equilibrated concentrate pH
- `result["concentrate_si"]` — SI for 9 minerals (Calcite, Aragonite, Dolomite, Gypsum, Anhydrite, Barite, Celestite, Fluorite, SiO₂(a))
- `result["feed_si"]` — same 9 minerals for feed stream

---

### 6.7 `POST /api/auto-select-membrane` (Lines 526–542)

**Input:** `SystemCalcInput`

Delegates to `MembraneRecommender().recommend(data.dict())`. Returns `best_membrane` (string) and `max_recovery` (= `target_recovery_pct / 100`).

---

### 6.8 `GET /api/membranes` (Lines 544–552)

No input. Returns:
```json
{
  "ro_membranes": [...],
  "uf_modules": [...]
}
```
Sourced from `MembraneDatabase.list_ro_membranes()` and `MembraneDatabase.list_uf_modules()`.

---

### 6.9 `POST /api/generate-calculation-report` (Lines 554–672)

**Input:** `SystemCalcInput`

1. Runs the appropriate engine path (same routing as 6.6).
2. Attaches `aging_results`, `pfd_svg`, `pfd_png`, `physics_results`, `project_details`, `units` to the result dict.
3. Calls `ReportGenerator().generate_calculation_report(result, tmp_docx.name)` to produce a `.docx` file.
4. Converts `.docx` → `.pdf`:
   - **Windows:** `docx2pdf` via subprocess
   - **Linux/Docker:** `libreoffice --headless --convert-to pdf`
5. **Watermarking** (Lines 616–655): Uses `PyMuPDF (fitz)` to overlay a rotated semi-transparent "PERMIONICS" text (45°, grey, `fill_opacity=0.15`) at the centre of every page.
6. Returns the PDF as a `FileResponse` with `Content-Disposition: attachment; filename="PACE_Calculation_Report.pdf"`. The temp file is deleted after streaming via `BackgroundTask`.

---

### 6.10 `POST /api/recommend-membrane` (Lines 674–682)

**Input:** `SystemCalcInput`

Returns full ranked membrane recommendations with scores from `MembraneRecommender().recommend(data.dict())`. See `membrane_recommender.md` for scoring logic.

---

### 6.11 `POST /api/simulate-aging` (Lines 1160–1210)

**Input:** `AgingSimInput`

Routes to `_run_projection_core()` (shared with `/api/calculate-system-physics`).

**CIP interval conversion:**
```python
cip_interval_months = 0 if cip_interval_days == 0 else max(1, round(cip_interval_days / 30))
```
`n_years = max(1, design_life_months // 12)`

Returns physics engine output reshaped for the Membrane Aging tab:
- `aging_profile` (monthly snapshots)
- `cip_events`
- `end_of_life_month`
- `dominant_mechanism`
- `mechanism_totals`
- `element_autopsy`
- `baseline_pressure_bar`
- `annual_snapshots`

---

### 6.12 `POST /api/calculate-system-physics` (Lines 1215–1318)

**Input:** `PhysicsCalcInput`

Routes to `_run_projection_core()`. Additionally:

**SDI / TOC auto-inference from feed water** (Lines 1227–1230):
```python
if fq.sdi15 == 3.0 and feed.get("tss", 0) > 0:
    fq.sdi15 = min(feed["tss"] * 0.5, 6.0)      # TSS → SDI proxy
if fq.toc_mg_l == 2.0 and feed.get("toc", 0) > 0:
    fq.toc_mg_l = feed["toc"]
```

**Year selection merging** (Lines 1265–1306): For the selected projection year, the physics snapshot metrics are merged into the baseline system result:
- `feed_pressure_bar` replaced with projected value
- `perm_tds` = `baseline_tds × nsp`
- `sec_kwh_m3` = `baseline_sec + (projected_sec − year0_sec)`
- `npf`, `nsp`, `fri`, `b_irr`, `physics_year` injected into summary

For 2-pass systems, Pass 2 summary is scaled by the ratios: `pressure_ratio`, `tds_ratio`, `kwh_ratio` derived from the physics snapshot vs. Year 0.

Returns: full merged result + `physics_results` + `physics_selected_year` + `concentrate_si` + `concentrate_ph`.

---

## 7. `_run_projection_core` — Shared Physics Projection Engine (Lines 778–1155)

Both `/api/simulate-aging` and `/api/calculate-system-physics` call this function, guaranteeing identical results for the same physical scenario.

### 7.1 Ion Extraction from feed_water dict (Lines 816–835)

| PACE `feed_water` key | Physics engine ion key |
|---|---|
| `calcium` | `Ca` |
| `magnesium` | `Mg` |
| `sodium` | `Na` |
| `potassium` | `K` |
| `chloride` | `Cl` |
| `sulfate` | `SO4` |
| `bicarbonate` | `HCO3` |
| `barium` | `Ba` |
| `strontium` | `Sr` |
| `fluoride` | `F` |
| `silica` | `SiO2` |
| `boron` | `B` |
| `nitrate` | `NO3` |
| `phosphate` | `PO4` |
| `ammonium` | `NH4` |
| `aluminium` | `Al` |
| `iron` | `Fe` |
| `manganese` | `Mn` |

### 7.2 Baseline Calculation

Runs `SystemEngine` with the full input dict (same routing as `/api/calculate-system`). For 2P-RO systems, `pass1_results` is used as the physics baseline.

### 7.3 Recycle Feed Ion Handling (Lines 890–946)

Three-tier fallback for blended feed composition when recycle is active:

| Tier | Source | Condition |
|---|---|---|
| Primary | `baseline["recycle"]["blended_feed_ions"]` | Solver output available |
| Secondary | `baseline["feed_water_used"]` | Blended feed dict available |
| Tertiary (fallback) | Analytical CF-scaling | Both solver paths fail |

**Analytical fallback formula:**
$$CF = \frac{1}{1 - R/100}$$
$$TDS_{conc} = TDS_{fresh} \times CF$$
$$Q_{recycle} = Q_{fresh} \times r_{recycle} \times R/100$$
$$w_{blend} = \frac{Q_{fresh} \times TDS_{fresh} + Q_{recycle} \times TDS_{conc}}{(Q_{fresh} + Q_{recycle}) \times TDS_{fresh}}$$
$$C_{blend,i} = C_{feed,i} \times w_{blend}$$

### 7.4 Year 0 Snapshot Override (Lines 1108–1117)

After the physics engine runs, the Year 0 snapshot is forcibly overwritten with the true combined system baseline:
- `recovery` = true system recovery (from `system_summary` for 2P, or `summary` for 1P)
- `npf = 1.0`, `nsp = 1.0` (ASTM D4516-19a baseline definition)
- `perm_flow`, `feed_pressure_bar`, `perm_tds`, `sec_kwh_m3` patched from the combined system result

### 7.5 Physics Engine Call (Lines 1051–1072)

```python
phys_engine.run_physics_projection(
    baseline_ro_result, feed_ions, temp_c, ph, membrane_model,
    stages, vessels_per_stage, elements_per_vessel,
    target_recovery_pct, feed_flow_m3h, n_years,
    feed_quality, cip_config, antiscalant_dosed,
    recycle_feed_ions, bulk_si
)
```

`bulk_si` is the compact SI dict `{calcite, gypsum, barite, silica}` computed from concentrate PHREEQC.

---

## 8. Ion Field Name Mapping (Frontend → Backend → Engines)

| UI Field | `FeedWaterData` | `feed_water` dict key | Engine ion key |
|---|---|---|---|
| Calcium | `calcium` | `calcium` | `Ca` |
| Magnesium | `magnesium` | `magnesium` | `Mg` |
| Sodium | `sodium` | `sodium` | `Na` |
| Potassium | `potassium` | `potassium` | `K` |
| Chloride | `chloride` | `chloride` | `Cl` |
| Sulphate | `sulfate` | `sulfate` | `SO4` |
| Bicarbonate | `bicarbonate` | `bicarbonate` | `HCO3` |
| Barium | `barium` | `barium` | `Ba` |
| Strontium | `strontium` | `strontium` | `Sr` |
| Fluoride | `fluoride` | `fluoride` | `F` |
| Silica | `silica` | `silica` | `SiO2` |
| Nitrate | `nitrate` | `nitrate` | `NO3` |
| Phosphate | `phosphate` | `phosphate` | `PO4` |
| Ammonium | `ammonium` | `ammonium` | `NH4` |
| Aluminium | `aluminium` | `aluminium` | `Al` |
| Iron | `iron` | `iron` | `Fe` |
| Manganese | `manganese` | `manganese` | `Mn` |

---

## 9. Traceability

| Logic | Lines | Tier | Citation |
|---|---|---|---|
| Charge Balance Error formula | 296–320 | External | Standard analytical chemistry [APHA Standard Methods] |
| CBE 2% threshold for balance check | 330 | Internal Method | Industry standard acceptance criterion |
| Auto-injection of Na⁺/Cl⁻ to balance | 334–342 | Internal Method | Permionics practice |
| LSI ≈ Calcite SI | 250 | External | Thermodynamically equivalent in PHREEQC |
| Concentrate pH: log10(HCO₃_conc/HCO₃_feed) | 435–436 | External | Henderson-Hasselbalch / carbonate equilibrium |
| CF fallback for pH when no HCO₃ data | 440 | Internal Method | Conservative approximation |
| Watermark opacity 0.15, angle 45° | 635–637 | Internal Method | Permionics branding |
| TSS → SDI proxy: `min(TSS × 0.5, 6.0)` | 1228 | Internal Method | Approximate SDI from TSS for data-poor inputs |
| Basic Auth credential env-var fallback | 53–54 | Internal Method | Secure override pattern |
