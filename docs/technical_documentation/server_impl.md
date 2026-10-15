# PACE — `server_impl.py` Technical Documentation

**File:** `backend/server_impl.py` | 1,185 lines | 49,956 bytes

---

## 1. Purpose & Scope

`server_impl.py` is the FastAPI application layer for PACE. It defines all REST API endpoints, input validation schemas (Pydantic models), and the shared physics projection core (`_run_projection_core`). It also contains the complete auto-balance / charge-balance correction algorithm and the PHREEQC-based scaling SI retrieval for the scaling tab.

**Note:** This file contains the API routing and orchestration logic. Calculation physics are delegated to the backend engine modules. The exception is the auto-balance logic, which is implemented inline in this file.

---

## 2. API Endpoints

| Endpoint | Method | Engine Called | Purpose |
|---|---|---|---|
| `/api/calculate-scaling` | POST | `phreeqpython` (direct) | PHREEQC SI for feed water |
| `/api/auto-balance` | POST | Inline (this file) | Charge balance + auto correction |
| `/api/process-recommendation` | POST | `ProcessRecommendationEngine` | Process technology selection |
| `/api/calculate-system` | POST | `SystemEngine` | RO/NF/2P-RO simulation |
| `/api/auto-select-membrane` | POST | `SystemEngine` + all membranes | Legacy membrane selection |
| `/api/recommend-membrane` | POST | `MembraneRecommender` | Scored membrane recommendation |
| `/api/simulate-aging` | POST | `_run_projection_core` → `PhysicsAgingEngine` | Multi-year physics projection (aging tab) |
| `/api/calculate-system-physics` | POST | `_run_projection_core` → `PhysicsAgingEngine` | Multi-year physics projection (year-wise tab) |
| `/api/generate-calculation-report` | POST | `SystemEngine` + `ReportGenerator` | PDF report generation |
| `/api/membranes` | GET | `MembraneDatabase` | Membrane and UF module listing |

---

## 3. PHREEQC-Based Scaling Calculation: `/api/calculate-scaling` (Lines 225–276)

**Purpose:** Runs a full PHREEQC speciation at feed conditions and returns SI values for 13 mineral phases.

**PHREEQC solution definition (Lines 229–250):**

| Field | PHREEQC format | Notes |
|---|---|---|
| `units` | `mg/L` | — |
| `temp` | `data.temperature` | °C |
| `pH` | `data.ph` | — |
| `Ca`, `Mg`, `Na`, `K` | direct mg/L | — |
| `N(-3)` | `{ammonium} as NH4` | NH₄⁺ as N in -3 oxidation state |
| `S(6)` | `{sulfate} as SO4` | SO₄²⁻ as S in +6 oxidation state |
| `Alkalinity` | `{bicarbonate} as CaCO3` | HCO₃ input as CaCO₃ equivalents |
| `N(5)` | `{nitrate} as NO3` | NO₃⁻ as N in +5 oxidation state |
| `Si` | `{silica} as SiO2` | Si as SiO₂ |
| `P` | `{phosphate} as PO4` | Phosphorus as PO₄ |

**Note:** Alkalinity entered as CaCO₃ equivalents. This differs from `aging_engine.py` which sometimes enters alkalinity as HCO₃ directly. The CaCO₃ format is the PHREEQC standard for titration alkalinity.

**SI values returned:**

| Key | Mineral Phase |
|---|---|
| `gypsum_si` | Gypsum (CaSO₄·2H₂O) |
| `calcite_si` | Calcite (CaCO₃) |
| `aragonite_si` | Aragonite (CaCO₃ polymorph) |
| `barite_si` | Barite (BaSO₄) |
| `lsi` | **LSI = Calcite SI** (comment: "approximated by Calcite SI in pure systems") |
| `celestite_si` | Celestite (SrSO₄) |
| `fluorite_si` | Fluorite (CaF₂) |
| `anhydrite_si` | Anhydrite (CaSO₄) |
| `silica_si` | Amorphous silica SiO₂(a) |
| `iron_si` | Fe(OH)₃(a) |
| `aluminium_si` | Al(OH)₃(a) |
| `manganese_si` | Pyrolusite (MnO₂) |
| `calcium_phosphate_si` | Hydroxyapatite |

**Important note on LSI:** The code comment states "LSI is approximated by Calcite SI in pure systems." PHREEQC's `sol.si("Calcite")` is the rigorous thermodynamic Saturation Index for calcite — it is the Langelier Saturation Index by definition (LSI = SI_calcite). The approximation label is a code comment artefact; the value is thermodynamically exact for the PHREEQC-computed speciation. [VERIFIED — External: PHREEQC documentation, USGS OFR 99-4259]

**Memory cleanup:** `sol.forget()` called after each solution to release PHREEQC memory.

**Error handling:** Any exception → HTTP 500 with exception detail.

**Source:** [VERIFIED — External: Parkhurst & Appelo (2013), USGS Techniques and Methods, Book 6, Chapter A43]

---

## 4. Auto-Balance / Charge-Balance Correction: `/api/auto-balance` (Lines 278–372)

**Purpose:** Computes the Charge Balance Error (CBE) of the feed water analysis and automatically balances it by injecting Na⁺ or Cl⁻ if CBE > 2%.

### 4.1 Alkalinity Split (Lines 303–311)

Bicarbonate field is in mg/L **as CaCO₃**:
$$\text{alk\_meq} = \frac{\text{bicarbonate\_mg/L\_as\_CaCO}_3}{50.04}$$

At pH < 8.3 (all alkalinity as HCO₃⁻):
$$\text{hco3\_meq} = \text{alk\_meq}, \quad \text{co3\_meq} = 0$$

At pH ≥ 8.3 (HCO₃⁻/CO₃²⁻ split):
$$\text{fraction\_CO}_3 = \frac{10^{pH - 10.3}}{1 + 10^{pH - 10.3}}$$
$$\text{co3\_meq} = \text{alk\_meq} \times \text{fraction\_CO}_3$$
$$\text{hco3\_meq} = \text{alk\_meq} - \text{co3\_meq}$$

The constant 10.3 is the pKa2 of carbonic acid at 25°C (used as the CO₃²⁻/HCO₃⁻ equivalence point).

**Source:** Standard carbonate alkalinity speciation. [VERIFIED — External: Stumm & Morgan, Aquatic Chemistry, 3rd ed.]

### 4.2 Cation Sum (Lines 313–321)

$$\Sigma_{cat} = \frac{Ca}{40.08} \times 2 + \frac{Mg}{24.31} \times 2 + \frac{Na}{22.99} + \frac{K}{39.10} + \frac{NH_4}{18.04} + \frac{Ba}{137.33} \times 2 + \frac{Sr}{87.62} \times 2 \text{ meq/L}$$

### 4.3 Anion Sum (Lines 323–330)

$$\Sigma_{an} = \frac{Cl}{35.45} + \frac{SO_4}{96.06} \times 2 + \text{hco3\_meq} + \text{co3\_meq} \times 2 + \frac{NO_3}{62.00} + \frac{F}{19.00} + \frac{PO_4}{94.97} \times 3 \text{ meq/L}$$

### 4.4 Charge Balance Error (Lines 332–334)

$$CBE_{meq} = \Sigma_{cat} - \Sigma_{an}$$
$$CBE\% = \frac{CBE_{meq}}{\max(\Sigma_{cat} + \Sigma_{an},\ 0.1)} \times 100$$

### 4.5 Auto-Correction Algorithm (Lines 344–357)

**Threshold:** If $|CBE\%| \leq 2.0$ → status = "BALANCED", no correction.

**If $|CBE\%| > 2.0$:** status = "ADJUSTED":
- If $CBE_{meq} > 0$ (excess cations → inject Cl⁻):
$$\Delta C_{Cl} = CBE_{meq} \times MW_{Cl} / z_{Cl} = CBE_{meq} \times 35.45 \text{ mg/L}$$
- If $CBE_{meq} < 0$ (excess anions → inject Na⁺):
$$\Delta C_{Na} = |CBE_{meq}| \times MW_{Na} / z_{Na} = |CBE_{meq}| \times 22.99 \text{ mg/L}$$

**Why Na⁺ or Cl⁻?** These are the most common unmeasured ions in field water analyses (sodium in cation-deficient analyses from missing sodium measurement; chloride in anion-deficient analyses). Using these ions is the industry convention for charge-balance completion. [INTERNAL METHOD — consistent with standard hydrochemical practice]

**Source:** Charge balance error formula: standard hydrochemical practice. [VERIFIED — External: Freeze & Cherry, Groundwater (1979), Appendix]

---

## 5. Physics Projection Core: `_run_projection_core` (Lines 688–1017)

**Purpose:** Shared function called by both `/api/simulate-aging` and `/api/calculate-system-physics`. Ensures both endpoints use identical physics engine inputs.

### 5.1 Ion Extraction (Lines 726–745)

Maps frontend field names to engine ion keys:
- `calcium` → `Ca`, `magnesium` → `Mg`, `sodium` → `Na`, `potassium` → `K`
- `chloride` → `Cl`, `sulfate` → `SO4`, `bicarbonate` → `HCO3`
- `barium` → `Ba`, `strontium` → `Sr`, `fluoride` → `F`
- `silica` → `SiO2`, `boron` → `B`, `nitrate` → `NO3`
- `phosphate` → `PO4`, `ammonium` → `NH4`, `aluminium` → `Al`
- `iron` → `Fe`, `manganese` → `Mn`

### 5.2 Baseline Year 0 Calculation (Lines 757–791)

Runs a full system simulation at Year 0 (clean membrane) using the same technology train as the projection (including UF pre-treatment, 2P-RO, recycle, conditioning). Produces `baseline_ro` — the reference state for all ASTM normalisation calculations.

### 5.3 Recycle Feed Ion Resolution (Lines 809–854)

For concentrate recycle systems, the blended feed ion concentrations (not fresh feed) must be used for fouling/scaling calculations. Three-level fallback:

1. **Primary:** Extract `blended_feed_ions` from converged solver result `baseline["recycle"]["blended_feed_ions"]`
2. **Secondary:** Extract from `baseline["feed_water_used"]` if TDS > fresh feed TDS
3. **Tertiary fallback (analytical, Lines 844–853):**

$$CF = \frac{1}{\max(1.0 - R_{frac},\ 0.05)}$$
$$Q_{recycle} = Q_{fresh} \times \text{recycle\_ratio} \times R_{frac}$$
$$Q_{blend} = Q_{fresh} + Q_{recycle}$$
$$\text{blend\_weight} = \frac{Q_{fresh} \times TDS_{fresh} + Q_{recycle} \times CF \times TDS_{fresh}}{Q_{blend} \times TDS_{fresh}}$$
$$C_{blend,i} = C_{fresh,i} \times \text{blend\_weight}$$

**Source:** [INTERNAL METHOD — analytical CF-based fallback; comment notes it is less accurate than solver-derived blended ions]

### 5.4 Bulk SI Calculation for Physics Engine (Lines 889–921)

Runs PHREEQC on the Year 0 concentrate ions to obtain bulk SI values for calcite, gypsum, barite, and amorphous silica. These are passed to `PhysicsAgingEngine` as `bulk_si` for the wall SI calculations.

PHREEQC format: identical to `/api/calculate-scaling` (Section 3 above).

Returns: `{"calcite": SI, "gypsum": SI, "barite": SI, "silica": SI}`

### 5.5 Year 0 Snapshot Correction (Lines 984–1008)

After physics engine returns, Year 0 snapshot values are overwritten with true baseline system metrics:

```python
snaps[0]["recovery"] = true_recovery
snaps[0]["npf"] = 1.0  # ASTM baseline — always 1.0
snaps[0]["nsp"] = 1.0  # ASTM baseline — always 1.0
snaps[0]["perm_flow"] = true_perm
snaps[0]["feed_pressure_bar"] = true_base_pressure
snaps[0]["perm_tds"] = true_base_tds
snaps[0]["sec_kwh_m3"] = true_base_sec
```

For Years 1–N: recovery and perm_flow are overwritten to match true system values. NPF and NSP are taken directly from the physics engine (ASTM D4516-19a formula, see `physics_aging_engine.md`).

**Rationale:** The physics engine calibrates A₀ to reproduce Year 0 recovery internally (via bisection), but the system-level summary (especially 2P-RO, recycle) must reflect the combined system metrics, not just the Pass 1 or element-level values.

---

## 6. CIP Interval Conversion (Lines 1034–1035, `/api/simulate-aging`)

$$\text{cip\_interval\_months} = \begin{cases} 0 & \text{if cip\_interval\_days} = 0 \text{ (dynamic trigger)} \\ \max(1, \text{round}(\text{cip\_interval\_days} / 30)) & \text{otherwise} \end{cases}$$

---

## 7. SDI-from-TSS Heuristic (Lines 1089–1090, `/api/calculate-system-physics`)

If SDI not explicitly set (= default 3.0) and TSS > 0:
$$SDI_{15} = \min(\text{TSS} \times 0.5,\ 6.0)$$

**Source:** [INTERNAL METHOD — empirical approximation; TSS-to-SDI conversion is feed-quality-specific and not universally applicable; flagged as a default heuristic]

---

## 8. Authentication & Security

Basic HTTP Authentication via `BasicAuthASGIMiddleware` (Lines 35–88). Credentials sourced from environment variables `API_USERNAME` and `API_PASSWORD`. All non-OPTIONS requests require valid credentials.

CORS: Wildcard origin regex (`".*"`) — accepts all origins.

---

## 9. PDF Report Generation (Lines 467–582)

Report generation flow:
1. Run system simulation (same routing as `/api/calculate-system`)
2. Generate `.docx` via `ReportGenerator.generate_calculation_report()`
3. Convert to PDF:
   - Windows: `docx2pdf` (local testing)
   - Linux/Docker: `libreoffice --headless --convert-to pdf`
4. Apply "PERMIONICS" watermark via `PyMuPDF` (fitz):
   - Text rendered at 60 pt Helvetica, 30% opacity, centered on each page
5. Return PDF as `FileResponse` with background cleanup task

**Source:** [INTERNAL METHOD — reporting/output generation layer; no new physics]

---

## 10. Change / Validation History

| Issue | Description | Current State |
|---|---|---|
| Year 0 snapshot mismatch | Physics engine Year 0 used element-level pressure, not system summary pressure | Fixed: `_run_projection_core` overwrites Year 0 snapshot with true baseline metrics |
| 2P-RO summary propagation | Pass 1 summary incorrectly used as system summary for 2P-RO | Fixed: `ro_results` dict constructed from `pass1_results` + `system_summary` override |
| Recycle feed ions | Analytics CF-scaling used instead of solver-converged blended ions | Fixed: three-level fallback; primary = solver result |
| Auto-balance threshold | No dead-band; minor imbalances triggered corrections | Fixed: 2% CBE threshold; balanced if |CBE%| ≤ 2 |

---

## 11. Source Tags

| Item | Tier | Citation |
|---|---|---|
| PHREEQC speciation | External | Parkhurst & Appelo (2013), USGS Techniques and Methods |
| LSI = Calcite SI | External | PHREEQC documentation |
| Carbonate alkalinity split | External | Stumm & Morgan, Aquatic Chemistry (1996) |
| CBE formula | External | Freeze & Cherry, Groundwater (1979) |
| Na/Cl auto-balance injection | Internal Method | Industry convention |
| SDI-from-TSS heuristic | Internal Method | Empirical approximation |
| Analytical recycle fallback | Internal Method | CF-based approximation |
| Year 0 snapshot correction | Internal Method | ASTM D4516-19a anchoring |
