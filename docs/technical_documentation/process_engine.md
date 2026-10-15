# PACE — `process_engine.py` Technical Documentation

**File:** `backend/process_engine.py` | 413 lines | 15,932 bytes
**Class:** `ProcessRecommendationEngine`
**Source of truth:** Direct source code analysis

---

## 1. Purpose & Scope

`process_engine.py` is the **decision-intelligence layer** of PACE. Given a raw feed water characterisation (TDS, ions, fouling indicators, application type), it runs a seven-phase sequential decision tree to output:

- A **primary technology train** recommendation (e.g. `UF+RO`, `2P-RO`, `High pH RO`)
- An **alternate configuration**
- **Pretreatment flags** (mandatory upstream steps)
- **Scaling risks** at the target recovery (via live PHREEQC calls)
- A **confidence score** reflecting completeness of the input data

It does **not** size the system — it only recommends the process route. Sizing is handled by `system_engine.py` after the user accepts the recommendation.

**API endpoint:** `/api/process-recommendation`
**Called via:** `server_impl.py` → `ProcessRecommendationEngine(pp).run(data)`

---

## 2. Input Model: `ProcessInputData` (Lines 5–46)

| Field | Type | Units | Category |
|---|---|---|---|
| `feed_tds` | float | mg/L | **Required** |
| `target_tds` | float | mg/L | **Required** |
| `target_recovery` | float | % | **Required** |
| `feed_ph` | float | — | Optional (default 7.5) |
| `feed_temp` | float | °C | Optional (default 25.0) |
| `source_type` | str | — | Optional (auto-inferred) |
| `sdi_15` | float | — | Fouling |
| `turbidity` | float | NTU | Fouling |
| `toc` | float | mg/L | Fouling |
| `color_ptco` | float | PtCo | Fouling |
| `iron_total` | float | mg/L | Fouling |
| `manganese` | float | mg/L | Fouling |
| `free_cl2` | float | mg/L | Fouling |
| `oil_grease` | float | mg/L | Halt condition |
| `cod` | float | mg/L | Halt condition |
| `bod` | float | mg/L | Halt condition |
| `ca`, `mg_ion`, `na`, `cl`, `so4`, `hco3`, `k`, `ba`, `sr`, `f`, `sio2`, `boron`, `no3`, `po4`, `nh4` | float | mg/L | Ions (default 0.0) |
| `application` | str | — | `UPW`, `PHARMA`, `BOILER_FEED`, `DRINKING`, `ZLD` |
| `target_flow` | float | m³/h | Informational only |

---

## 3. Engine State Object

Initialised at construction; mutated by each phase:

```python
state = {
    "primary_config":        None,   # Final recommended train
    "ro_variant":            None,   # Membrane class (BWRO-LP, BWRO-MP, etc.)
    "second_pass_required":  False,
    "second_pass_high_ph":   False,
    "alternate_config":      None,
    "scaling_risks":         {},     # {mineral: {si, risk}} from Phase 4
    "flags":                 [],     # Process-level advisory messages
    "pretreatment_flags":    [],     # Mandatory pretreatment messages
    "confidence": {
        "score":          100,       # Starts at 100; deducted per missing input
        "level":          "HIGH",    # HIGH ≥ 80 | MEDIUM ≥ 55 | LOW < 55
        "missing_inputs": []
    },
    "halt": False                    # Hard stop for unusable feed water
}
```

---

## 4. Execution Pipeline

```
run(data)
  ├── Phase 0: _phase_0_confidence()       — score missing inputs, apply defaults
  ├── Phase 1: _phase_1_source_type()      — halt check: wastewater / oil & grease
  ├── Phase 2: _phase_2_fouling()          — UF mandatory/recommended decision
  ├── Phase 3: _phase_3_primary_process()  — TDS-based technology draft selection
  ├── Phase 4: _phase_4_scaling()          — PHREEQC scaling at target CF
  │   (skipped if no ionic data; score −20)
  ├── Phase 5: _phase_5_permeate_quality() — 2-pass / boron / application check
  ├── Phase 6: _phase_6_nf_refinement()    — NF override logic
  └── Phase 7: _phase_7_final_assembly()   — Combine all flags → final output
```

Each phase after Phase 0 and Phase 1 checks `self.state["halt"]`; if `True`, execution stops and the partial state is returned immediately.

---

## 5. Phase 0 — Confidence Scoring (Lines 109–131)

Confidence starts at 100 and is **deducted** for each missing or defaulted input:

| Missing Input | Deduction | Default Applied |
|---|---|---|
| `feed_ph` | −10 | 7.5 |
| `sdi_15` AND `turbidity` both absent | −12 | None |
| `feed_temp` | −5 | 25.0°C |
| `application` | −5 | None |
| `source_type` (auto-inferred in Phase 1) | −10 | Inferred |
| No ionic data (Phase 4 skipped) | −20 | None |

**Confidence level thresholds:**

| Score | Level |
|---|---|
| ≥ 80 | HIGH |
| 55–79 | MEDIUM |
| < 55 | LOW |

**Flag generated if pH defaulted:**
> `"Default pH 7.5 applied. Carbonate scaling risk may be underestimated."`

---

## 6. Phase 1 — Source Type & Hard-Stop Checks (Lines 133–154)

### 6.1 Source Type Auto-Inference (when not supplied)

| Feed TDS (mg/L) | Inferred `source_type` |
|---|---|
| > 20,000 | `SEAWATER` |
| 3,001–20,000 | `BRACKISH_GW` |
| ≤ 3,000 AND (turbidity > 2 NTU OR TOC > 5 mg/L) | `SURFACE` |
| Otherwise | `LOW_TDS` |

### 6.2 Hard-Stop (HALT) Conditions

| Condition | Trigger | Action |
|---|---|---|
| Wastewater source + high biological load | `("WW" in source_type OR "WASTEWATER" in source_type)` AND (`COD > 150` OR `BOD > 20`) | **HALT** — biological pretreatment required |
| Oil & Grease | `oil_grease > 5 mg/L` | **HALT** — DAF or separator required |

When `halt = True`, the engine returns immediately with pretreatment flags set; no technology recommendation is made.

---

## 7. Phase 2 — UF Integration Decision (Lines 156–202)

Sets `state["uf_integration"] = True` (UF mandatory or recommended) based on fouling indicators:

### 7.1 SDI-Based Rules

| SDI₁₅ Value | Decision |
|---|---|
| > 5 | UF **mandatory** |
| > 3 | UF **mandatory** |
| > 1 AND source is SURFACE or WASTEWATER | UF **mandatory** |

### 7.2 Turbidity Fallback (when SDI not available)

| Turbidity (NTU) | Decision |
|---|---|
| > 1.0 | UF **mandatory** |
| > 0.5 | UF **recommended** |
| No SDI, no turbidity, SURFACE source | UF **mandatory** + flag |

### 7.3 Other Fouling Indicators

| Parameter | Threshold | Decision |
|---|---|---|
| TOC | > 10 mg/L | UF mandatory + biofouling control flag |
| TOC | 5–10 mg/L | UF recommended |
| Color | > 50 PtCo | UF mandatory + humic substances flag |
| Iron (total) | > 0.3 mg/L | UF mandatory + oxidation/filtration flag |
| Manganese | > 0.05 mg/L | Oxidation pretreatment flag (no UF mandate) |
| Free Cl₂ | > 0.1 mg/L | Dechlorination required flag (SMBS or Carbon) |
| Oil & Grease | 1–5 mg/L | UF mandatory |
| Source = wastewater | any | UF mandatory |

> **Note:** `uf_integration` = `True` means UF is either mandatory OR recommended. The distinction (mandatory vs. recommended) is conveyed through the flags text, not a separate state variable.

---

## 8. Phase 3 — Primary Technology Draft (Lines 204–232)

TDS-based primary configuration selection. Result is a **draft** — Phase 6 may upgrade NF → RO.

| Feed TDS (mg/L) | Draft Config | RO Variant Class |
|---|---|---|
| < 200 | NF | None |
| 200–500 | NF | `BWRO-LP` |
| 501–2,000 | NF | `BWRO-LP` |
| 2,001–5,000 | RO | `BWRO-MP` |
| 5,001–10,000 | RO | `BWRO-HP` |
| 10,001–35,000 | RO | `HP-BWRO` |
| > 35,000 | RO | `SWRO` |

For SWRO: flag appended — `"ERD strongly recommended for SWRO systems > 500 m3/day."`

**Implied rejection by RO variant (used in Phase 5):**

| Variant | Assumed Rejection |
|---|---|
| `SWRO` | 99.5% |
| `HP-BWRO` | 98.5% |
| All others | 98.0% |

---

## 9. Phase 4 — Scaling Analysis via PHREEQC (Lines 234–318)

### 9.1 Concentration Factor Calculation

$$CF = \frac{1}{1 - R/100}$$

where $R$ = `target_recovery` (%).

All ion concentrations are multiplied by $CF$ before passing to PHREEQC — this simulates the **concentrate composition** at the target recovery.

### 9.2 PHREEQC Solution Assembly (`_run_phreeqc_cf`, Lines 234–268)

| Ion | PHREEQC Field | Format |
|---|---|---|
| Ca | `Ca` | `value × CF` |
| Mg | `Mg` | `value × CF` |
| Na | `Na` | `value × CF` |
| K | `K` | `value × CF` |
| Cl | `Cl` | `value × CF` |
| SO₄ | `S(6)` | `"{value × CF} as SO4"` |
| HCO₃ (as CaCO₃) | `Alkalinity` | `"{value × CF} as CaCO3"` |
| Ba | `Ba` | `value × CF` |
| Sr | `Sr` | `value × CF` |
| F | `F` | `value × CF` |
| SiO₂ | `Si` | `"{value × CF} as SiO2"` |
| NH₄ | `N(-3)` | `"{value × CF} as NH4"` |
| NO₃ | `N(5)` | `"{value × CF} as NO3"` |
| PO₄ | `P` | `"{value × CF} as PO4"` |

PHREEQC returns full thermodynamic SI for 9 mineral phases: `Calcite`, `Gypsum`, `Anhydrite`, `Barite`, `Celestite`, `Fluorite`, `SiO2(a)`, `Aragonite`, `Dolomite`.

Solution is discarded after reading (`sol.forget()`).

### 9.3 Scaling Risk Evaluation (`_eval_scaling`, Lines 270–302)

SI-to-risk mapping (SI thresholds):

| Mineral | NONE | LOW | MODERATE | HIGH | CRITICAL |
|---|---|---|---|---|---|
| Calcite | < 0.0 | — | 0.0–0.5 | 0.5–1.0 | > 1.0 |
| Gypsum | < 0.0 | — | 0.0–0.3 | 0.3–0.5 | > 0.5 |
| Anhydrite | < 0.0 | — | 0.0–0.3 | 0.3–0.5 | > 0.5 |
| Barite | < −0.2 | −0.2–0.0 | 0.0–0.0 | 0.0–0.3 | > 0.3 |
| Celestite | < 0.0 | — | 0.0–0.2 | 0.2–0.4 | > 0.4 |
| Fluorite | < 0.0 | — | 0.0–0.5 | — | > 0.5 |
| SiO₂(a) | < −0.1 | −0.1–0.0 | 0.0–0.0 | 0.0–0.2 | > 0.2 |
| Aragonite, Dolomite | — | — | — | — | INFORMATIONAL if SI > −0.3 |

> **Note:** SI values ≤ −99.0 are silently skipped (PHREEQC returns −99.999 when a phase is undefined for the solution composition).

**Critical scaling actions:**

- Any CRITICAL mineral → flag: `"CRITICAL {mineral} scaling detected at {R}% target recovery. Recovery may not be feasible."`
- If `SiO2(a)` is CRITICAL → `state["high_ph_ro_hint"] = True` + flag suggesting high pH RO

---

## 10. Phase 5 — Permeate Quality & Two-Pass Logic (Lines 320–350)

### 10.1 Single-Pass TDS Estimate

$$TDS_{perm,est} = TDS_{feed} \times (1 - R_{rej})$$

where $R_{rej}$ is the variant rejection (see Phase 3 table).

### 10.2 Two-Pass Trigger Conditions

| Condition | Trigger | Flag |
|---|---|---|
| $TDS_{perm,est} > TDS_{target} \times 1.1$ | 2-pass required | Estimated TDS exceeds target |
| Application = `UPW` or `PHARMA` | 2-pass required | Application mandates 2P-RO |
| Application = `BOILER_FEED` AND `target_tds ≤ 10` | 2-pass required | Application mandates 2P-RO |
| `boron > 1.0 mg/L` | 2-pass required + `second_pass_high_ph = True` | Boron removal requires 2P-RO at pH 9.5–10.5 |

> **Note (Line 345):** The boron check contains `or True` — making it unconditional whenever boron > 1.0 mg/L regardless of application type. This is intentional per the code comment: `# if target < 0.5`.

---

## 11. Phase 6 — NF Override / Refinement (Lines 352–381)

Only runs if the Phase 3 draft is `"NF"`.

**NF estimated permeate TDS (fixed 60% rejection assumption):**
$$TDS_{perm,NF} = TDS_{feed} \times (1 - 0.60)$$

**NF → RO upgrade triggers (any one sufficient):**

| Trigger | Reason |
|---|---|
| `second_pass_required = True` | Two-pass requirement incompatible with NF |
| Application in `[UPW, PHARMA, BOILER_FEED]` AND `target_tds < 50` | Strict quality demand |
| $TDS_{perm,NF} > TDS_{target} \times 1.1$ | NF cannot meet permeate quality target |

If none of the above: NF confirmed, flag appended:
> `"NF confirmed suitable. Estimated permeate TDS: {X} mg/L. NF offers higher recovery at lower operating pressure for this feed."`

---

## 12. Phase 7 — Final Assembly (Lines 383–413)

Combines UF flag, two-pass flag, and NF/RO draft into the final train recommendation:

| Draft | Two-Pass? | UF? | `primary_config` | `alternate_config` |
|---|---|---|---|---|
| NF | — | — | `NF` | `RO` |
| RO | No | No | `RO` | `UF+RO` |
| RO | No | Yes | `UF+RO` | `RO with enhanced cartridge filtration` |
| RO | Yes | No | `2P-RO` | `RO + EDI/MB` |
| RO | Yes | Yes | `UF+RO` | `2P-RO with enhanced cartridge filtration` |

**Post-assembly overrides:**

| Condition | Override |
|---|---|
| `application = "ZLD"` | Flag: `"ZLD Application: RO max recovery 85%. Downstream brine concentrator/crystalliser required."` |
| `high_ph_ro_hint = True` | `primary_config` → `"High pH RO"`, `alternate_config` → `"UF+RO (at reduced recovery)"` |

> **Note:** When `high_ph_ro_hint` fires, it overrides whatever Phase 7 assembled, including any UF/2-pass combination.

---

## 13. Complete Output Structure

```json
{
  "primary_config":        "UF+RO",
  "ro_variant":            "BWRO-HP",
  "second_pass_required":  false,
  "second_pass_high_ph":   false,
  "alternate_config":      "RO with enhanced cartridge filtration",
  "scaling_risks": {
    "Calcite": {"si": 0.72, "risk": "HIGH"},
    "Barite":  {"si": 0.15, "risk": "HIGH"}
  },
  "flags": [
    "CRITICAL Barite scaling detected at 75% target recovery.",
    "Estimated single-pass TDS (120) within target."
  ],
  "pretreatment_flags": [
    "Iron > 0.3 mg/L. Oxidation and filtration required upstream.",
    "Free Chlorine > 0.1 mg/L. Dechlorination required (SMBS or Carbon)."
  ],
  "confidence": {
    "score": 75,
    "level": "MEDIUM",
    "missing_inputs": ["sdi_15", "turbidity"]
  },
  "halt": false
}
```

---

## 14. Edge Cases & Guard Clauses

| Situation | Handling |
|---|---|
| No ionic data at all | Phase 4 skipped; confidence −20; flag added |
| PHREEQC returns SI = −99.999 | `sival <= -99.0` check silently skips mineral |
| Oil & grease exactly 5 mg/L | `>= 1 and <= 5` → UF mandatory (line 196); `> 5` → HALT (line 151) — these two conditions are adjacent, not overlapping |
| `source_type` not supplied | Auto-inferred from TDS + turbidity/TOC; confidence −10 |
| `feed_ph` not supplied | Defaulted to 7.5; confidence −10; flag warns about carbonate underestimation |
| `boron > 1.0` regardless of application | 2-pass always triggered (line 345: `or True`) |
| `high_ph_ro_hint` present | Overrides Phase 7 final assembly completely |

---

## 15. Traceability

| Logic | Source | Method |
|---|---|---|
| Concentration Factor formula | Standard membrane engineering | [VERIFIED — External] |
| PHREEQC SI calculation | Parkhurst & Appelo (2013) USGS TM Book 6 Ch. A43 | [VERIFIED — External] |
| SI threshold limits (risk levels) | Permionics engineering judgment | [INTERNAL METHOD] |
| TDS-to-process-class mapping | Permionics engineering judgment | [INTERNAL METHOD] |
| UF mandate thresholds (SDI, turbidity) | Industry standards (AWWA M46, DuPont ROSA guidelines) | [INTERNAL METHOD — consistent with industry] |
| NF rejection assumption (60%) | Conservative NF permeate estimate | [INTERNAL METHOD] |
| 2-pass 10% TDS margin (`target_tds × 1.1`) | Permionics engineering tolerance | [INTERNAL METHOD] |
| Boron 2-pass threshold (1.0 mg/L) | WHO drinking water guideline 0.5 mg/L with safety factor | [INTERNAL METHOD] |
| Confidence scoring deductions | Permionics engineering judgment | [INTERNAL METHOD] |
