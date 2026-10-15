# PACE — `system_engine.py` Technical Documentation

**File:** `backend/system_engine.py` | 993 lines | 47,620 bytes

---

## 1. Purpose & Scope

`system_engine.py` orchestrates multi-technology treatment trains (UF→RO, UF→NF, 2-Pass RO, concentrate recycle). It wraps `ROEngine.simulate_system()` with a bisection pressure solver, economic calculations, and NF-specific feed quality checks. It is the primary calculation engine called by the `/api/calculate-system` endpoint.

**Pipeline:** Feed water → UF sizing (if train includes UF) → bisection pressure solver → RO/NF simulation → NF concentrate scaling check → Economics → Output.

---

## 2. Module-Level Function: `_compute_nf_concentrate_scaling` (Lines 13–133)

**Purpose:** Saturation Indices (SI) for 6 scalants in NF concentrate using the Davies equation for activity coefficients.

**Inputs:**

| Parameter | Units | Description |
|---|---|---|
| `conc_ions` | mg/L | NF concentrate ion concentrations |
| `feed_ph` | — | Feed pH (conservative surrogate for concentrate pH) |
| `temp_c` | °C | Temperature |

**Ionic strength:**
$$I = 0.5 \times \sum_i \frac{C_i}{MW_i \times 1000} \times z_i^2 \text{ mol/L}$$

Ions and charges: Ca(z=2), Mg(2), Na(1), K(1), Ba(2), Sr(2), Cl(1), SO4(2), HCO3(1), NO3(1), F(1), PO4(3), NH4(1), Fe(2), Mn(2)

**Davies equation (A=0.509 at 25°C):**
$$\log \gamma(z) = -0.509 \times z^2 \times \left(\frac{\sqrt{I}}{1+\sqrt{I}} - 0.3I\right)$$
$$\gamma(z) = 10^{\log\gamma(z)}$$

$\sqrt{I} = \sqrt{\max(I, 10^{-12})}$ (prevents zero)

**Source:** Davies (1938, 1962) equation — extension of Debye–Hückel valid to I ≈ 0.5 M. [VERIFIED — External: Davies C.W., Ion Association, Butterworths (1962)]

**Why Davies over Debye–Hückel:** RO/NF concentrate ionic strengths routinely exceed 0.1 M (the valid limit of simple Debye–Hückel). Davies adds the $0.3I$ linear correction term extending validity to ~0.5 M.

**Scalant SI formulas (exactly as coded):**

| Scalant | $K_{sp}$ | Ion Product |
|---|---|---|
| CaSO₄ (Gypsum) | 4.93×10⁻⁵ mol²/L² | $[Ca][SO_4]\gamma(2)^2$ |
| BaSO₄ (Barite) | 1.08×10⁻¹⁰ mol²/L² | $[Ba][SO_4]\gamma(2)^2$ |
| SrSO₄ (Celestite) | 3.44×10⁻⁷ mol²/L² | $[Sr][SO_4]\gamma(2)^2$ |
| CaF₂ (Fluorite) | 3.45×10⁻¹¹ mol³/L³ | $[Ca][F]^2\gamma(2)\gamma(1)^2$ |

$$SI = \log_{10}(IP / K_{sp}) \text{ if } IP > 0, \text{ else } -99.0$$

**SiO₂ Amorphous:**
$$S_{SiO_2} = 100.0 + \max(0, T_{°C} - 25) \times 0.5 \text{ mg/L}$$
$$SiO_2\% = \frac{C_{SiO_2,conc}}{S_{SiO_2}} \times 100$$

Risk: HIGH > 80%; MODERATE 60–80%; LOW otherwise.

**Source:** $K_{sp}$ values from NIST thermodynamic databases. SiO₂ solubility: [INTERNAL METHOD — linear T-correction at 0.5 mg/L/°C above 25°C]

**CaCO₃ Langelier SI:**
$$\text{pH}_s = (pK_2 - pK_{sp}) - \log[Ca] - \log[HCO_3] - \log\gamma(2) - \log\gamma(1)$$
$$LSI = \text{pH}_{feed} - \text{pH}_s$$

where $pK_2 = 10.33$, $pK_{sp} = 8.48$ (both at 25°C).

**Source:** Langelier (1936), J. AWWA 28(10):1500–1521. [VERIFIED — External]

**Risk classification:**

| SI | Risk | Antiscalant Required |
|---|---|---|
| > 0 | HIGH | Yes |
| > −0.5 | MODERATE | No |
| ≤ −0.5 | LOW | No |

---

## 3. Class: `SystemEngine`

### 3.1 `calculate_system` (Lines 141–546)

**Osmotic pressure estimate (Line 212):**
$$\pi_{est} = \frac{\sum_i C_i}{1000} \times 0.7 \text{ bar}$$

(Rule of thumb: ~7 bar per 10,000 mg/L TDS)

**Bisection pressure solver (Lines 217–240):**
- $P_{low} = \max(1.0, \pi_{est} - 5.0)$
- $P_{high} = \max(120.0, \pi_{est} + 60.0)$
- Tolerance: 0.005 (0.5% on recovery fraction)
- Max 25 iterations
- $P_{mid} = (P_{low} + P_{high})/2$ → full `simulate_system` → compare recovery to target

**NF feed quality checks (Lines 248–385):**

| Parameter | CRITICAL | WARNING |
|---|---|---|
| TDS (mg/L) | > 8000 | 5000–8000 |
| SDI₁₅ | > 5 | > 3 |
| Fe total (mg/L) | > 0.3 | > 0.05 |
| Free Cl₂ (ppm) | > 0.1 | > 0.05 |
| TOC (mg/L) | > 10 | > 3 |
| pH | < 4 | < 6 or > 9 |

**Hard stop NF-W-HYD-10:** $P_{feed} > 41$ bar → CRITICAL, halt.

---

### 3.2 Economic Equations (Lines 397–505)

**Membrane element price:**

| Membrane type | Price (INR/element) |
|---|---|
| NF | 19,200 |
| SWRO or rejection ≥ 99.5% | 30,240 |
| BWRO (default) | 26,880 |

**CAPEX:**
$$C_{equip} = C_{memb} + C_{vessels} + C_{HP} + C_{BP} + C_{UF\_modules} + C_{UF\_pumps}$$
$$C_{IC} = C_{equip} \times f_{IC} \quad (\text{default } f_{IC} = 0.15)$$
$$C_{cont} = (C_{equip} + C_{IC}) \times f_{cont} \quad (\text{default } f_{cont} = 0.10)$$
$$CAPEX = C_{equip} + C_{IC} + C_{cont}$$

**UF OPEX:**
$$h_{pa} = 0.90 \times 8760 \text{ h/yr}$$
$$E_{UF,pa} = (kW_{feed} + kW_{BW}) \times h_{pa} \times \text{tariff}$$
$$CEB_{kg/pa} = 0.007 \times Q_{UF,net} \times h_{pa} \text{ (7 g/m}^3\text{ net UF permeate)}$$
$$C_{CEB,pa} = CEB_{kg/pa} \times 30.0 \text{ (INR 30/kg)}$$
$$UF_{mem,repl,pa} = C_{UF,modules} / 7 \text{ yr (default lifetime)}$$

**RO OPEX:**
$$E_{RO,pa} = \text{total\_kW} \times h_{pa} \times \text{tariff}$$
$$RO_{mem,repl,pa} = C_{memb} / 5 \text{ yr (default lifetime)}$$
$$OPEX_{pa} = E_{RO,pa} + RO_{mem,repl,pa} + UF_{mem,repl,pa} + C_{CEB,pa}$$

**Capital Recovery Factor:**
$$CRF = \frac{d(1+d)^n}{(1+d)^n - 1}$$

$d = 0.10$ (discount rate), $n = 20$ years (default).

**Cost per KL:**
$$Q_{annual} = Q_{perm} \times h_{pa}$$
$$C_{total,pa} = CAPEX \times CRF + OPEX_{pa}$$
$$\text{Cost/KL} = \frac{C_{total,pa}}{Q_{annual}} \text{ INR/KL}$$

**Source:** CRF formula: standard engineering economics. [VERIFIED — External] INR unit costs: [INTERNAL METHOD — Permionics market pricing]

---

### 3.3 `calculate_system_with_recycle` (Lines 548–693)

**Blended feed concentrations:**
$$Q_{blend} = Q_{fresh} + Q_{recycle}$$
$$C_{blend,i} = \frac{C_{fresh,i} \times Q_{fresh} + C_{recycle,i} \times Q_{recycle}}{Q_{blend}}$$

**Convergence:** $\delta = |Q_{perm} - Q_{perm,prev}| / Q_{perm,prev} < 0.002$; max 15 iterations.

**Effective recovery:**
$$R_{eff} = \frac{Q_{perm}}{Q_{fresh\_feed}}$$

---

### 3.4 `simulate_two_pass_system` (Lines 695–917)

**Pass 2 auto-sizing (Lines 788–812):**
$$\text{perm\_per\_elem} = \frac{37.0 \text{ m}^2 \times 20 \text{ LMH}}{1000} = 0.74 \text{ m}^3/\text{h/element}$$
$$n_{elem,min} = \max\left(1, \left\lceil \frac{Q_{P1} \times R_{P2,target}}{0.74} \right\rceil + 1\right)$$

**Overall 2-Pass recovery:**
$$R_{overall} = \frac{Q_{P2,perm}}{Q_{fresh}}$$

**2-Pass SEC:**
$$SEC_{2P} = \frac{P1_{kW} + P2_{kW}}{Q_{P2,perm}} \text{ kWh/m}^3$$

---

## 4. Change / Validation History

| Issue | Description | Current State |
|---|---|---|
| LSI pH correction | Feed pH used as surrogate for concentrate pH — conservative | Concentrate pH correction exists only in `aging_engine.py`, not here |
| NF SI activity | Davies used (valid to ~0.5 M) | [UNVERIFIED — REQUIRES ENGINEERING REVIEW: Davies may underestimate activity at high-salinity NF concentrate] |
| SiO₂ T-correction | 0.5 mg/L/°C linear correction above 25°C | [INTERNAL METHOD] |

---

## 5. Source Tags Summary

| Equation | Tier | Citation |
|---|---|---|
| Davies equation | External | Davies (1962), Ion Association |
| Ksp values (gypsum, barite, celestite, fluorite) | External | NIST thermodynamic databases |
| SiO₂ solubility (100 mg/L + 0.5/°C) | Internal Method | Permionics calibration |
| Langelier SI | External | Langelier (1936), J. AWWA |
| Bisection solver | Internal Method | Standard numerical method |
| CRF formula | External | Standard engineering economics |
| INR cost rates | Internal Method | Permionics market pricing |
| Pass 2 auto-sizing (0.74 m³/h/elem) | Internal Method | Based on 37 m² @ 20 LMH |
