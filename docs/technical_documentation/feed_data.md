# PACE — Feed Data Module Technical Documentation

**File:** `ui_ux_design/script.js` (Feed Data tab functions)
**Source of truth:** Direct source code analysis

---

## 1. Purpose & Scope

The Feed Data tab is the **primary input screen** of PACE. Users enter all feed water parameters here — physical parameters, ionic composition, and fouling indicators. The module then:

1. **Validates** physical parameters (pH, temperature, recovery, free Cl₂)
2. **Calculates** ion chemistry live: meq/L, CaCO₃ equivalents, TDS, ionic strength, osmotic pressure, CBE
3. **Runs scaling analysis** via the PHREEQC backend
4. **Generates pretreatment recommendations** from fouling indicators
5. **Syncs all data** downstream to the Decline Projection panel and other tabs

---

## 2. Input Fields (Feed Data Tab)

### 2.1 Physical Parameters

| HTML ID | Parameter | Units | Validation Range |
|---|---|---|---|
| `temp` | Feed temperature | °C (or °F if unit changed) | 0–80°C hard; 10–40°C soft warning |
| `ph` | Feed pH | — | 0.1–14 hard; 6.5–8.5 soft warning |
| `recovery` | Target recovery | % | 0–100 hard; >80 warning |
| `cl2` | Free chlorine | mg/L | >0.1 triggers dechlorination warning |
| `sdi` | SDI-15 | — | Used for pretreatment recommendation |
| `turbidity` | Turbidity | NTU | Used for pretreatment recommendation |
| `water-type` | Source water type | — | Dropdown; drives osmotic coefficient |

### 2.2 Cation Input Fields (`.cation` class)

| HTML ID | Ion | MW (g/mol) | z |
|---|---|---|---|
| `ca` | Ca²⁺ | stored in `data-mw` | 2 |
| `mg` | Mg²⁺ | stored in `data-mw` | 2 |
| `na` | Na⁺ | stored in `data-mw` | 1 |
| `k` | K⁺ | stored in `data-mw` | 1 |
| `nh4` | NH₄⁺ | stored in `data-mw` | 1 |
| `ba` | Ba²⁺ | stored in `data-mw` | 2 |
| `sr` | Sr²⁺ | stored in `data-mw` | 2 |

### 2.3 Anion Input Fields (`.anion` class)

| HTML ID | Ion | MW (g/mol) | z |
|---|---|---|---|
| `cl` | Cl⁻ | stored in `data-mw` | 1 |
| `so4` | SO₄²⁻ | stored in `data-mw` | 2 |
| `hco3` | HCO₃⁻ | stored in `data-mw` | 1 |
| `co3` | CO₃²⁻ | stored in `data-mw` | 2 |
| `no3` | NO₃⁻ | stored in `data-mw` | 1 |
| `f` | F⁻ | stored in `data-mw` | 1 |
| `po4` | PO₄³⁻ | stored in `data-mw` | 3 |

### 2.4 Neutral / Trace Species (not classed, individual DOM IDs)

| HTML ID | Species | MW used | Notes |
|---|---|---|---|
| `sio2` | SiO₂ | 60.08 | Added to Σci (osmotic); meq = 0 |
| `fe` | Fe (total) | 55.845 | Added to TDS + osmotic sum |
| `al` | Al | 26.98 | Added to TDS + osmotic sum |
| `mn` | Mn | 54.938 | Added to TDS + osmotic sum |

---

## 3. `validatePhysicalParameters` (Lines 2284–2342)

Called every time a physical parameter changes. Writes inline status messages via `setMsg()`.

| Parameter | Hard Clamp | Soft Warning | OK Range |
|---|---|---|---|
| pH | [0.1, 14] | < 6.5 or > 8.5 | 6.5–8.5 |
| Temperature | None | < 10°C or > 40°C (after unit conversion to °C) | 10–40°C |
| Recovery | None | > 80% | 0–80% |
| Free Cl₂ | None | > 0.1 mg/L → "Dechlorination required" | ≤ 0.1 |

> **Note:** Temperature is always converted to °C for validation using `conversions.temp.toBase(rawTemp, currentUnits.temp)` before range checks, regardless of display unit.

---

## 4. `calculateChemistry` (Lines 2344–2532)

Runs live on every ion input change. Triggered with `showAllResults = true` only when the user explicitly runs a full analysis.

### 4.1 Per-Ion Calculations (for every `.cation` and `.anion`)

**milli-equivalents per litre:**
$$meq/L = \frac{C_{mg/L} \times z}{MW}$$

**CaCO₃ equivalent:**
$$CaCO_3 = meq/L \times 50$$

(Equivalent weight of CaCO₃ = 50 g/eq)

**Molar concentration:**
$$mol/L = \frac{C_{mg/L}}{MW \times 1000}$$

**Ionic strength contribution:**
$$I += 0.5 \times mol/L \times z^2$$

### 4.2 TDS Calculation

$$TDS_{calc} = \sum_{cations} C_i + \sum_{anions} C_i + C_{Al} + C_{Fe} + C_{Mn}$$

### 4.3 Conductivity Estimate

$$EC \approx \frac{TDS_{calc}}{0.65} \quad \text{(µS/cm)}$$

**Source:** [INTERNAL METHOD — empirical TDS/EC ratio of 0.65]

### 4.4 Osmotic Pressure Calculation

$$\pi = \varphi \times R_{gas} \times T_K \times \Sigma C_i$$

where:
- $R_{gas} = 0.0831$ L·bar/(mol·K)
- $T_K = T_{°C} + 273.15$ K
- $\Sigma C_i$ = total molar concentration of all ions + neutral species (mol/L):

$$\Sigma C_i = \sum_{ions} \frac{C_{mg/L}}{MW \times 1000} + \frac{C_{Fe}}{55845} + \frac{C_{Al}}{26980} + \frac{C_{Mn}}{54938} + \frac{C_{SiO_2}}{60080}$$

- $\varphi$ = osmotic coefficient from `getOsmoticCoefficient()` (see §5)

Result stored in `window.lastCalculatedOsmoticPressure` (bar) and converted to display units via `conversions.pressure.fromBase()`.

**Source:** Van't Hoff equation [VERIFIED — External]; φ values: [INTERNAL METHOD]

### 4.5 Charge Balance Error (CBE) — Frontend Calculation

$$\Sigma_{cat} = \sum_{cations} meq/L, \quad \Sigma_{an} = \sum_{anions} meq/L$$

$$CBE\% = \frac{\Sigma_{cat} - \Sigma_{an}}{\Sigma_{cat} + \Sigma_{an}} \times 100$$

**CBE Status thresholds (frontend display only):**

| |CBE%| Range | Status | Action |
|---|---|---|
| 0 | NO DATA | No ions entered |
| ≤ 5% | ACCEPT | Pass |
| 5–10% | ACCEPT (WARNING) | Warn |
| 10–15% | LOW CONFIDENCE | Warn + suggest synthetic balance |
| > 15% | REJECTED | Reject |

**Synthetic balance suggestion (shown when 10–15%):**
- Cation-heavy (CBE > 0): Suggest Cl⁻ addition = `(ΣCat − ΣAn) × 35.45` mg/L
- Anion-heavy (CBE < 0): Suggest Na⁺ addition = `(ΣAn − ΣCat) × 22.99` mg/L

> **Important:** This is a **display-only** CBE computed in the browser. The actual backend auto-balance uses a 2% threshold (see `server.py` §6.4). The frontend uses a more lenient 5% ACCEPT threshold.

---

## 5. `getOsmoticCoefficient` (Lines 2611–2630)

Returns $\varphi$ based on the selected `water-type` dropdown:

| `data-source-type` attribute | φ |
|---|---|
| `LOW_TDS` | 0.99 |
| `WELL_WATER` | 0.965 |
| `BRACKISH_GW` | 0.93 |
| `SURFACE` | 0.93 |
| `SURFACE_SDI3` | 0.93 |
| `WASTEWATER` | 0.95 |
| `WASTEWATER_UF` | 0.95 |
| `SEAWATER` | 0.90 |
| `SEAWATER_BEACH` | 0.90 |
| `RO_PERMEATE` | 0.99 |
| Default (fallback) | 0.93 |

**Source:** [INTERNAL METHOD — Permionics calibrated values]

---

## 6. `runPhreeqcCalculation` (Lines 1408–1549)

Triggered by the "Run Scaling Analysis" button (`run-phreeqc-btn`). Collects all feed water fields and POSTs to `/api/calculate-scaling`.

### 6.1 Payload

All values are read directly from their HTML input element IDs in mg/L:
`temp`, `ph`, `ca`, `mg`, `na`, `cl`, `so4`, `hco3`, `sr`, `f`, `sio2`, `ba`, `k`, `nh4`, `co3`, `no3`, `al`, `fe`, `mn`, `po4`

### 6.2 SI Display

**% Saturation from SI:**
$$\% Sat = 10^{SI} \times 100\%$$

Displayed as: `"0.215 (164%)"` — SI value followed by % saturation in parentheses.

Values ≤ −99.0 are masked as `"--"` (PHREEQC undefined mineral for that solution).

**Color coding via `updateSiColor`:**

| Condition | Colour | Indicator |
|---|---|---|
| SI > threshold (0) | Red (`--error-color`) | + ⚠️ emoji |
| SI between (threshold − 0.5) and threshold | Orange (`--warning-color`) | — |
| SI ≤ threshold − 0.5 | Green (`--success-color`) | — |

### 6.3 SI Chart (Chart.js)

Bar chart with 11 mineral SI values. Bars are coloured:
- **Red** (`rgba(239,68,68,0.85)`) when SI > 0 (supersaturated)
- **Indigo** (`rgba(79,70,229,0.85)`) when SI ≤ 0 (undersaturated)

Null values (masked `--`) are passed as `null` to Chart.js to prevent axis distortion.

---

## 7. `calculatePreTreatment` (Lines 2546–2604)

Runs automatically at the end of `calculateChemistry()`. Generates a pretreatment recommendation list based on fouling indicators.

### 7.1 SDI-Based Rules

| SDI₁₅ | Recommendation |
|---|---|
| > 5 | UF + 5 μm cartridge filter (Mandatory) |
| 3–5 | Dual media filter + 5 μm cartridge filter |
| 0–3 | 5 μm cartridge filter only |

### 7.2 Turbidity-Based Rules

| Turbidity (NTU) | Recommendation |
|---|---|
| > 1 | Coagulation/Flocculation + Dual media filter |
| 0.5–1 | Dual media filter + cartridge filter |

### 7.3 Other Fouling Indicators

| Parameter | Threshold | Recommendation |
|---|---|---|
| Iron (`fe`) | > 0.05 mg/L | Aeration or chlorination + media filtration + dechlorination |
| Free Cl₂ (`cl2`) | > 0.1 mg/L | SMBS dosing for dechlorination |

**Source:** [INTERNAL METHOD — consistent with industry standards AWWA M46]

---

## 8. `syncAllParametersFromFeed` (Lines 2659–2736)

Propagates Feed Data tab values downstream to the Decline Projection panel when switching tabs.

| Feed Data field | Synced to Decline field |
|---|---|
| `recovery` | `dec-recovery` |
| `calc-tds` (calculated TDS) | `dec-tdsref` |
| Σ all ions (fallback if not yet calculated) | `dec-tdsref` |
| `temp` (first sync only) | `dec-tact` |
| `window.lastCalcResult.ro_results.summary.perm_flow` | `dec-q0` (converted to display units) |
| `window.lastCalcResult.ro_results.summary.feed_pressure_bar` | `dec-p0` (converted to display units) |
| Osmotic pressure | `dec-out-osm` via `syncOsmoticPressureFromFeed()` |

After syncing, calls `runDeclineProjection()` automatically.

---

## 9. `runFullValidation` (Line 2606–2609)

Entry point for the "Analyse Feed Water" button. Runs:
1. `validatePhysicalParameters()` — inline field validation
2. `calculateChemistry(true)` — full chemistry calculation with all results shown

---

## 10. SI Display Output Fields

| HTML Element ID | Mineral |
|---|---|
| `si-calcite` | Calcite |
| `si-gypsum` | Gypsum |
| `si-anhydrite` | Anhydrite |
| `si-barite` | Barite |
| `si-srso4` | Celestite (SrSO₄) |
| `si-caf2` | Fluorite (CaF₂) |
| `si-silica` | SiO₂(a) |
| `si-fe` | Fe(OH)₃(a) |
| `si-al` | Al(OH)₃(a) |
| `si-mn` | Pyrolusite (MnO₂) |
| `si-po4` | Hydroxyapatite (Ca₅(PO₄)₃OH) |

---

## 11. Summary Output Fields

| HTML Element ID | Displays |
|---|---|
| `calc-tds` | Calculated TDS (mg/L) |
| `calc-ec` | Estimated conductivity (µS/cm) |
| `sum-cat` | Σ cations (meq/L) |
| `sum-an` | Σ anions (meq/L) |
| `osmotic-pressure` | Osmotic pressure (display units) |
| `cbe-display` | CBE (%) with sign |
| `cbe-status` | ACCEPT / WARNING / REJECTED |
| `total-mgl` | Grand total (mg/L) |
| `total-meq` | Grand total (meq/L) |
| `total-caco3` | Grand total (mg/L as CaCO₃) |

---

## 12. Traceability

| Logic | Lines | Tier | Citation |
|---|---|---|---|
| meq/L = C×z/MW | 2362 | External | Standard analytical chemistry |
| CaCO₃ eq = meq/L × 50 | 2363 | External | Equivalent weight of CaCO₃ |
| Ionic strength = 0.5 × Σ(mol/L × z²) | 2376 | External | Debye-Hückel I definition |
| EC ≈ TDS / 0.65 | 2432 | Internal Method | Empirical ratio |
| Osmotic pressure: φ × R × T × ΣCi | 2464 | External | Van't Hoff |
| φ coefficients by water type | 2617–2629 | Internal Method | Permionics calibration |
| CBE% = (ΣCat−ΣAn)/(ΣCat+ΣAn) × 100 | 2487 | External | Standard analytical chemistry |
| % Saturation = 10^SI × 100 | 1483 | External | Definition of SI |
| SI ≤ −99 masked as "--" | 1482 | Internal Method | PHREEQC undefined mineral convention |
| Pretreatment SDI thresholds (3, 5) | 2562–2568 | Internal Method | Industry standard (AWWA M46) |
| Fe > 0.05 mg/L threshold | 2579 | Internal Method | Permionics operating guideline |
| TSS → SDI proxy in physics endpoint | server.py:1228 | Internal Method | `min(TSS × 0.5, 6.0)` |
