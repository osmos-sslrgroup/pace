# PACE — `conditioning.py` Technical Documentation

**File:** `backend/conditioning.py` | 58 lines | 2,496 bytes

---

## 1. Purpose & Scope

`conditioning.py` handles interstage chemical conditioning between Pass 1 and Pass 2 in a two-pass RO system. It performs three operations: CO₂ degassing (binary, 100% stripping), chemical dose estimation for pH adjustment, and stoichiometric ion balance update after dosing.

**Pipeline position:** Pass 1 permeate → (degassing + pH adjustment) → Pass 2 feed.

---

## 2. Every Equation

### 2.1 `compute_chemical_dose` (Lines 9–23)

**Purpose:** Estimates active chemical dose (mg/L) to shift pH by ΔpH.

**Logic:**
```
current_ph = ions.get("pH", 7.0)
if |current_ph - target_ph| < 0.1: return 0.0   (dead-band)
ΔpH = target_ph - current_ph
if NaOH and ΔpH > 0: dose = ΔpH × 2.5 mg/L
if H₂SO₄ or HCl and ΔpH < 0: dose = |ΔpH| × 2.5 mg/L
else: dose = 0.0
```

**Constant:** 2.5 mg/L per pH unit — simplified empirical proportionality.

**Source:** [INTERNAL METHOD — simplified linear dose model; 2.5 mg/L/pH unit empirical constant; no buffer capacity or alkalinity correction modelled]

**Limitations:**
- No carbonate/alkalinity buffer capacity correction
- No temperature correction
- Dead-band of 0.1 pH prevents spurious dosing
- Mismatched chemical-direction returns 0.0

---

### 2.2 `apply_conditioning` (Lines 25–57)

**Purpose:** Applies CO₂ degassing and chemical dosing to Pass 1 permeate, returning conditioned ions.

**CO₂ degassing (line 40):**
$$C_{CO_2}^{new} = 0.0 \text{ mg/L}$$
(Binary: 100% stripping. No partial stripping model.)

**pH after dosing:** `ions["pH"] = target_ph` (set directly, no equilibrium calculation)

**Stoichiometric ion adjustments:**

| Chemical | Ion Added | Equation |
|---|---|---|
| NaOH | Na⁺ | $\Delta C_{Na} = \text{dose} \times (22.99/40.00)$ |
| H₂SO₄ | SO₄²⁻ | $\Delta C_{SO_4} = \text{dose} \times (96.06/98.08)$ |
| HCl | Cl⁻ | $\Delta C_{Cl} = \text{dose} \times (35.45/36.46)$ |

Molar mass ratios: NaOH→Na: 22.99/40.00 = 0.5748; H₂SO₄→SO₄: 96.06/98.08 = 0.9794; HCl→Cl: 35.45/36.46 = 0.9723

**Returns:** `(conditioned_ions, dose_mg_L, resulting_pH)`

---

## 3. Edge Cases

| Condition | Behavior |
|---|---|
| `enabled=False` | Returns original ions unchanged, dose=0 |
| CO₂ degassing disabled | CO₂ left at Pass 1 permeate level |
| Chemical = NaOH but ΔpH < 0 | dose = 0.0 (wrong direction) |
| |ΔpH| < 0.1 | dose = 0.0 (dead-band) |
| Pydantic object vs dict for `cond_cfg` | Both supported via try/except attribute access |

---

## 4. Change / Validation History

- CO₂ degassing is a binary 100% stripping assumption — no degassing efficiency or partial stripping model has been implemented.
- pH is set directly rather than computed from alkalinity + added base equilibrium. This is a simplification that produces correct dose volumes but does not model the actual pH profile accurately for high-alkalinity Pass 1 permeates.

---

## 5. Source Tags

| Item | Tier | Citation |
|---|---|---|
| Stoichiometric mass fractions | External | Standard inorganic chemistry |
| 2.5 mg/L per pH unit dose constant | Internal Method | Permionics empirical approximation |
| CO₂ degassing = 100% | Internal Method | Simplifying assumption; not physically modelled |
| Direct pH set | Internal Method | No equilibrium calculation |
